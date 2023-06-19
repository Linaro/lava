# Copyright (C) 2015-present Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import asyncio
import base64
import contextlib
import json
import signal
import weakref
from dataclasses import dataclass
from typing import Any

import aiohttp
import zmq
import zmq.asyncio
from aiohttp import web
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.utils.crypto import constant_time_compare

from lava_common.version import __version__
from lava_scheduler_app.models import Device, TestJob, Worker
from lava_server.cmdutils import LAVADaemonCommand
from linaro_django_xmlrpc.models import AuthToken

TIMEOUT = 5
FORMAT = "%(asctime)-15s %(levelname)7s %(message)s"


@dataclass
class Websocket:
    kind: str
    name: str
    socket: Any

    def __hash__(self):
        return hash((self.kind, self.name, id(self.socket)))


async def zmq_proxy(app):
    logger = app["logger"]

    context = zmq.asyncio.Context()

    logger.info("[INIT] Create input socket at %r", settings.INTERNAL_EVENT_SOCKET)
    pull = context.socket(zmq.PULL)
    pull.bind(settings.INTERNAL_EVENT_SOCKET)

    logger.info("[INIT] Create the pub socket at %r", settings.EVENT_SOCKET)
    pub = context.socket(zmq.PUB)
    pub.setsockopt(zmq.HEARTBEAT_IVL, 5000)
    pub.setsockopt(zmq.HEARTBEAT_TIMEOUT, 15000)
    pub.setsockopt(zmq.HEARTBEAT_TTL, 15000)
    pub.bind(settings.EVENT_SOCKET)

    if settings.EVENT_ADDITIONAL_SOCKETS:
        logger.info("[INIT] Creating the additional sockets:")
    additional_sockets = []
    for url in settings.EVENT_ADDITIONAL_SOCKETS:
        logger.info("[INIT]  * %r", url)
        sock = context.socket(zmq.PUSH)
        # Allow zmq to keep 10000 pending messages in each queue
        sock.setsockopt(zmq.SNDHWM, 10000)
        # Ask zmq to send heart beats
        # See api.zeromq.org/4-2:zmq-setsockopt#toc17
        sock.setsockopt(zmq.HEARTBEAT_IVL, 5000)
        sock.setsockopt(zmq.HEARTBEAT_TIMEOUT, 15000)
        sock.setsockopt(zmq.HEARTBEAT_TTL, 15000)
        # connect
        sock.connect(url)
        additional_sockets.append(sock)

    async def forward_event(msg):
        logger.debug("[PROXY] Forwarding: %s", msg)
        data = [s.decode("utf-8") for s in msg]
        futures = [
            pub.send_multipart(msg),
            *[s.send_multipart(msg, flags=zmq.DONTWAIT) for s in additional_sockets],
        ]

        # Filter on permissions
        topic = data[0]
        content = json.loads(data[4])
        if topic.endswith(".device"):
            device = await sync_to_async(Device.objects.get)(hostname=content["device"])
            for ws in set(app["websockets"]):
                # Only forward to users as workers will discard it
                if ws.kind == "user":
                    user = AnonymousUser()
                    if ws.name:
                        with contextlib.suppress(User.DoesNotExist):
                            user = await sync_to_async(User.objects.get)(
                                username=ws.name
                            )
                    if await sync_to_async(device.can_view)(user):
                        futures.append(ws.socket.send_json(data))

        elif topic.endswith(".testjob"):
            while True:
                try:
                    job = await sync_to_async(TestJob.objects.get)(id=content["job"])
                    break
                except TestJob.DoesNotExist:
                    await asyncio.sleep(1)
            for ws in set(app["websockets"]):
                if ws.kind == "user":
                    user = AnonymousUser()
                    if ws.name:
                        with contextlib.suppress(User.DoesNotExist):
                            user = await sync_to_async(User.objects.get)(
                                username=ws.name
                            )
                    if await sync_to_async(job.can_view)(user):
                        futures.append(ws.socket.send_json(data))
                elif ws.kind == "worker":
                    # Only forward event with the worker specified.
                    # Anyway other events are discarded by workers.
                    if ws.name == content.get("worker"):
                        futures.append(ws.socket.send_json(data))

        elif topic.endswith(".worker"):
            # Only forward to users as workers will discard it
            futures.extend(
                [
                    ws.socket.send_json(data)
                    for ws in set(app["websockets"])
                    if ws.kind == "user"
                ]
            )

        await asyncio.gather(*futures)

    with contextlib.suppress(asyncio.CancelledError):
        logger.info("[PROXY] waiting for events")
        while True:
            try:
                msg = await pull.recv_multipart()
                await forward_event(msg)
            except zmq.error.ZMQError as exc:
                logger.error("[PROXY] Received a ZMQ error: %s", exc)
                break

    # Carefully close the logging socket as we don't want to lose messages
    logger.info("[EXIT] Disconnect pull socket and process messages")
    endpoint = pull.getsockopt(zmq.LAST_ENDPOINT).decode("utf-8")
    logger.debug("[EXIT] unbinding from %r", endpoint)
    pull.unbind(endpoint)

    # UNIX signals
    def signal_handler(*_):
        logger.debug("[EXIT] Signal already handled, wait for the process to exit")

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, signal_handler)
    loop.add_signal_handler(signal.SIGTERM, signal_handler)

    while True:
        try:
            msg = await asyncio.wait_for(pull.recv_multipart(), TIMEOUT)
            await forward_event(msg)
        except zmq.error.ZMQError as exc:
            logger.error("[EXIT] Received a ZMQ error: %s", exc)
            break
        except asyncio.TimeoutError:
            logger.info("[EXIT] Timing out")
            break

    logger.info("[EXIT] Closing the sockets: the queue is empty")
    pull.close(linger=1)
    pub.close(linger=1)
    for socket in additional_sockets:
        socket.close(linger=1)
    context.term()


async def websocket_handler(request):
    logger = request.app["logger"]

    # Create the object and only then decide what to do with it
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Check Basic authentication
    name = None
    kind = "user"
    if request.headers.get("Authorization"):
        kind = "user"
        auth = request.headers["Authorization"]
        if not auth.startswith("Basic "):
            await ws.send_json({"error": "Only Basic authentication is supported"})
            await ws.close()
            return ws
        try:
            (name, secret) = (
                base64.standard_b64decode(auth[len("Basic ") :])
                .decode("utf-8")
                .split(":", 1)
            )
        except ValueError:
            await ws.send_json({"error": "Invalid basic authentication"})
            await ws.close()
            return ws
        user = await sync_to_async(AuthToken.get_user_for_secret)(name, secret)
        if user is None:
            await ws.send_json({"error": "Unknown user"})
            await ws.close()
            return ws

    elif request.headers.get("LAVA-Token"):
        kind = "worker"
        token = request.headers.get("LAVA-Token")
        name = request.headers.get("LAVA-Host")

        try:
            worker = await sync_to_async(Worker.objects.get)(hostname=name)
        except Worker.DoesNotExist:
            await ws.send_json({"error": "Unknown worker"})
            await ws.close()
            return ws
        if not constant_time_compare(token, worker.token):
            await ws.send_json({"error": "Invalid worker token"})
            await ws.close()
            return ws

    if name:
        logger.info("[WS] connection from %s %s@%s", kind, name, request.remote)
    else:
        logger.info("[WS] connection from %s %s", kind, request.remote)

    obj = Websocket(kind=kind, name=name, socket=ws)
    request.app["websockets"].add(obj)

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.ERROR:
                logger.exception(ws.exception())
    finally:
        request.app["websockets"].discard(obj)

    if obj.name:
        logger.info(
            "[WS] connection closed from %s %s@%s", obj.kind, obj.name, request.remote
        )
    else:
        logger.info("[WS] connection closed from %s %s", obj.kind, request.remote)
    return ws


async def websocket_healthz_handler(request):
    return web.json_response({"health": "good"})


async def on_startup(app):
    app["zmq_proxy"] = asyncio.create_task(zmq_proxy(app))


async def on_shutdown(app):
    # Stop the zmq proxy
    if app["zmq_proxy"] is not None:
        app["zmq_proxy"].cancel()
        await app["zmq_proxy"]

    for ws in set(app["websockets"]):
        await ws.socket.close(
            code=aiohttp.WSCloseCode.GOING_AWAY, message="Server shutdown"
        )


class Command(LAVADaemonCommand):
    help = "LAVA event publisher"
    default_logfile = "/var/log/lava-server/lava-publisher.log"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--host", default="*", help="host to bind to")
        parser.add_argument("--port", default=8001, type=int, help="port to bind to")

    def handle(self, *args, **options):
        self.setup_logging(
            "lava-publisher", options["level"], options["log_file"], FORMAT
        )

        self.logger.info("[INIT] Starting lava-publisher")
        self.logger.info("[INIT] Version %s", __version__)

        self.logger.info("[INIT] Dropping privileges")
        if not self.drop_privileges(options["user"], options["group"]):
            self.logger.error("[INIT] Unable to drop privileges")
            return

        if not settings.EVENT_NOTIFICATION:
            self.logger.error(
                "[INIT] 'EVENT_NOTIFICATION' is set to False, "
                "LAVA won't generated any events"
            )

        # Create the aiohttp application
        app = web.Application()

        # Variables
        app["logger"] = self.logger
        app["websockets"] = weakref.WeakSet()
        app["zmq_proxy"] = None

        # Routes
        app.add_routes([web.get("/ws/", websocket_handler)])
        app.add_routes([web.get("/ws/v1/healthz", websocket_healthz_handler)])

        # signals
        app.on_startup.append(on_startup)
        app.on_shutdown.append(on_shutdown)

        # Run the application
        self.logger.info(
            "[INIT] Listening on http://%s:%d", options["host"], options["port"]
        )
        web.run_app(app, host=options["host"], port=options["port"], print=False)
