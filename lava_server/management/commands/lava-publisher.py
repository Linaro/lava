# -*- coding: utf-8 -*-
# Copyright (C) 2015-present Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import aiohttp
from aiohttp import web
import asyncio
import contextlib
import signal
import weakref
import zmq
import zmq.asyncio
from zmq.utils.strtypes import u

from django.conf import settings

from lava_common.version import __version__
from lava_server.cmdutils import LAVADaemonCommand


TIMEOUT = 5
FORMAT = "%(asctime)-15s %(levelname)7s %(message)s"


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
        app["logger"].debug("[PROXY] Forwarding: %s", msg)
        data = [s.decode("utf-8") for s in msg]
        futures = [
            pub.send_multipart(msg),
            *[ws.send_json(data) for ws in app["websockets"]],
            *[s.send_multipart(msg, flags=zmq.DONTWAIT) for s in additional_sockets],
        ]
        await asyncio.gather(*futures)

    with contextlib.suppress(asyncio.CancelledError):
        logger.info("[PROXY] waiting for events")
        while True:
            try:
                msg = await pull.recv_multipart()
                await forward_event(msg)
            except zmq.error.ZMQError as exc:
                logger.error("[PROXY] Received a ZMQ error: %s", exc)

    # Carefully close the logging socket as we don't want to lose messages
    logger.info("[EXIT] Disconnect pull socket and process messages")
    endpoint = u(pull.getsockopt(zmq.LAST_ENDPOINT))
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
    logger.info("[WS] connection from %r", request.remote)

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app["websockets"].add(ws)

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.ERROR:
                logger.exception(ws.exception())
    finally:
        request.app["websockets"].discard(ws)

    logger.info("[WS] connection closed from %r", request.remote)
    return ws


async def on_startup(app):
    app["zmq_proxy"] = asyncio.create_task(zmq_proxy(app))


async def on_shutdown(app):
    # Stop the zmq proxy
    if app["zmq_proxy"] is not None:
        app["zmq_proxy"].cancel()
        await app["zmq_proxy"]

    for ws in set(app["websockets"]):
        await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message="Server shutdown")


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

        # signals
        app.on_startup.append(on_startup)
        app.on_shutdown.append(on_shutdown)

        # Run the application
        self.logger.info(
            "[INIT] Listening on http://%s:%d", options["host"], options["port"]
        )
        web.run_app(app, host=options["host"], port=options["port"], print=False)
