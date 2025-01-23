#!/usr/bin/python3
#
# Copyright (C) 2020-present Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import asyncio
import contextlib
import getpass
import json
import logging
import logging.handlers
import os
import sqlite3
import subprocess
import sys
import time
import traceback
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from json import loads as json_loads
from pathlib import Path
from shutil import rmtree
from signal import Signals
from typing import Any

import aiohttp
import sentry_sdk
import yaml

from lava_common.constants import DISPATCHER_DOWNLOAD_DIR
from lava_common.constants import WORKER_DIR as _WORKER_DIR_STR
from lava_common.exceptions import LAVABug
from lava_common.version import __version__
from lava_common.worker import get_parser, init_sentry_sdk
from lava_common.yaml import yaml_safe_load

###########
# Constants
###########
FINISH_MAX_DURATION = 120

TIMEOUT = 60 * 10  # http timeout to 10 minutes
WORKER_DIR = Path(_WORKER_DIR_STR)


#########
# Globals
#########
# Create the logger that will be configured later
logging.Formatter.convert = time.gmtime
LOG = logging.getLogger("lava-worker")
FORMAT = "%(asctime)-15s %(levelname)7s %(message)s"

ping_interval = 20
debug = False
tmp_dir = WORKER_DIR / "tmp"

# Stale configuration
STALE_CONFIG = {
    Path(DISPATCHER_DOWNLOAD_DIR): "{prefix}{job_id}",
    tmp_dir: "{prefix}{job_id}",
}

# URLs
URL_JOBS = "/scheduler/internal/v1/jobs/"
URL_WORKERS = "/scheduler/internal/v1/workers/"

THREAD_EXECUTOR = ThreadPoolExecutor(max_workers=8)
JOB_ASYNC_TASKS: set[asyncio.Task[None]] = set()


###########
# Helpers #
###########
def create_environ(env: str) -> dict[str, str]:
    """
    Generate the env variables for the job.
    """
    conf = yaml_safe_load(env) if env else None
    environ = dict(os.environ)
    if conf:
        if conf.get("purge", False):
            environ = {}
        # Remove some variables (that might not exist)
        for var in conf.get("removes", {}):
            with contextlib.suppress(KeyError):
                del environ[var]
        # Override
        environ.update(conf.get("overrides", {}))
    return environ


def get_prefix(cfg) -> str:
    if isinstance(cfg, dict):
        return cfg.get("prefix", "")
    return ""


@dataclass
class Response:
    status_code: int
    text: str

    def json(self) -> Any:
        return json_loads(self.text)


async def aiohttp_get(
    session: aiohttp.ClientSession,
    url: str,
    token: str | None,
    params: dict[str, str] | None = None,
) -> Response:
    if params is None:
        params = {}
    headers: dict[str, str] = {}
    if token is not None:
        headers["LAVA-Token"] = token

    try:
        async with session.get(url, params=params, headers=headers) as request:
            return Response(request.status, await request.text())
    except aiohttp.ClientError as exc:
        return Response(503, str(exc))


async def aiohttp_post(
    session: aiohttp.ClientSession, url: str, token: str | None, data: dict[str, str]
) -> Response:
    headers: dict[str, str] = {}
    if token is not None:
        headers["LAVA-Token"] = token

    try:
        async with session.post(url, data=data, headers=headers) as request:
            return Response(request.status, await request.text())
    except aiohttp.ClientError as exc:
        return Response(503, str(exc))


###############
# job helpers #
###############
def start_job(
    url: str,
    token: str,
    job_id: int,
    definition: str,
    device: str,
    dispatcher: str,
    env_str: str,
    env_dut: str,
    job_log_interval: int,
) -> int | None:
    """
    Start the lava-run process and return the pid
    """
    # Create the base directory
    dispatcher_cfg = yaml_safe_load(dispatcher)
    base_dir = tmp_dir / f"{get_prefix(dispatcher_cfg)}{job_id}"
    base_dir.mkdir(mode=0o755, exist_ok=True, parents=True)

    # Write back the job, device and dispatcher configuration
    (base_dir / "job.yaml").write_text(definition, encoding="utf-8")
    (base_dir / "device.yaml").write_text(device, encoding="utf-8")
    (base_dir / "dispatcher.yaml").write_text(dispatcher, encoding="utf-8")

    # Dump the environment variables in the tmp file.
    if env_dut:
        (base_dir / "env-dut.yaml").write_text(env_dut, encoding="utf-8")

    try:
        if debug:
            out_file = sys.stdout
            err_file = sys.stderr
        else:
            out_file = (base_dir / "stdout").open("w")
            err_file = (base_dir / "stderr").open("w")
        env = create_environ(env_str)
        args = [
            "lava-run",
            f"--device={base_dir / 'device.yaml'}",
            f"--dispatcher={base_dir / 'dispatcher.yaml'}",
            f"--output-dir={base_dir}",
            f"--job-id={job_id}",
            f"--url={url}",
            f"--token={token}",
            f"--job-log-interval={job_log_interval}",
        ]
        if debug:
            args.append("--debug")
        args.append(str(base_dir / "job.yaml"))

        if env_dut:
            args.append("--env-dut=%s" % (base_dir / "env-dut.yaml"))

        proc = subprocess.Popen(
            args, stdout=out_file, stderr=err_file, env=env, preexec_fn=os.setpgrp
        )
        return proc.pid
    except Exception as exc:  # pylint: disable=broad-except
        LOG.error("[%d] Unable to start: %s", job_id, args)
        # daemon must always continue running even if the job crashes
        if hasattr(exc, "child_traceback"):
            LOG.exception("[%d] %s", job_id, exc.child_traceback)
        else:
            LOG.exception("[%d] %s", job_id, exc)
            err_file.write("%s\n%s\n" % (exc, traceback.format_exc()))
        # The process has not started
        # The END message will be sent the next time
        # check_job_status is run
        return None


def rmtree_job_dir(dir_path: str) -> None:
    rmtree(dir_path, ignore_errors=True)


async def cleanup_job(prefix: str, job_id: int) -> None:
    loop = asyncio.get_running_loop()
    for directory, pattern in STALE_CONFIG.items():
        dir_name = pattern.format(prefix=prefix, job_id=job_id)
        dir_path = directory / dir_name
        if not dir_path.exists():
            continue
        LOG.debug("[%d] Removing %s", job_id, dir_path)
        await loop.run_in_executor(
            THREAD_EXECUTOR,
            rmtree_job_dir,
            str(dir_path),
        )

    LOG.debug("[%d] Finished cleanup", job_id)


#########
# Classes
#########
class Job:
    """Wrapper around a job process."""

    RUNNING, CANCELING, FINISHED = range(3)

    def __init__(self, row: sqlite3.Row):
        self.job_id: int = row["id"]
        self.pid: int = row["pid"]
        self.status: int = row["status"]
        self.prefix: str = row["prefix"]
        self.last_update: int = row["last_update"]
        self.token: str = row["token"]
        # Create the base directory
        self.base_dir = tmp_dir / "{prefix}{job_id}".format(
            prefix=self.prefix, job_id=str(self.job_id)
        )
        self.base_dir.mkdir(mode=0o755, exist_ok=True, parents=True)

    def errors(self) -> str:
        with contextlib.suppress(OSError, UnicodeDecodeError):
            return (self.base_dir / "stderr").read_text(
                encoding="utf-8", errors="replace"
            )
        return ""

    def description(self) -> str:
        with contextlib.suppress(OSError):
            return (self.base_dir / "description.yaml").read_text(
                encoding="utf-8", errors="backslashreplace"
            )
        return ""

    def result(self) -> dict[str, Any]:
        with contextlib.suppress(OSError, yaml.YAMLError):
            data = yaml_safe_load((self.base_dir / "result.yaml").read_bytes())
            if isinstance(data, dict):
                return data
        return {}

    def kill(self) -> None:
        # If the pid is 0, just skip because lava-run was not started
        if self.pid == 0:
            return
        os.kill(self.pid, Signals.SIGKILL)

    def terminate(self) -> None:
        # If the pid is 0, just skip because lava-run was not started
        if self.pid == 0:
            return
        os.kill(self.pid, Signals.SIGTERM)

    def is_running(self) -> bool:
        with contextlib.suppress(OSError):
            with open("/proc/%d/cmdline" % self.pid) as fd:
                return "lava-run" in fd.read()
        return False


class JobsDB:
    def __init__(self, dbname: str):
        self.conn = sqlite3.connect(dbname)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, pid INTEGER, status INTEGER, last_update INTEGER, prefix VARCHAR(100) DEFAULT '')"
        )
        self.conn.commit()
        # Migrate the schema only if needed
        sql = self.conn.execute("SELECT sql FROM sqlite_master").fetchone()["sql"]
        if "prefix" not in sql:
            self.conn.execute(
                "ALTER TABLE jobs ADD COLUMN prefix VARCHAR(100) DEFAULT ''"
            )
            self.conn.commit()
        if "token" not in sql:
            self.conn.execute(
                "ALTER TABLE jobs ADD COLUMN token VARCHAR(32) DEFAULT ''"
            )
            self.conn.commit()

        self.lock = asyncio.Lock()

    def create(
        self, job_id: int, pid: int, status: int, dispatcher_cfg: str, token: str
    ) -> Job | None:
        """
        When pid is 0, the pid is unknown
        """
        # Keep the prefix (if present) in the database to later delete
        # resources
        prefix = get_prefix(dispatcher_cfg)

        with contextlib.suppress(sqlite3.Error):
            self.conn.execute(
                "INSERT INTO jobs VALUES(?, ?, ?, ?, ?, ?)",
                (
                    str(job_id),
                    str(pid),
                    str(status),
                    str(int(time.monotonic())),
                    prefix,
                    token,
                ),
            )
            self.conn.commit()
            return self.get(job_id)
        return None

    def get(self, job_id: int) -> Job | None:
        row = self.conn.execute(
            "SELECT * FROM jobs WHERE id=?", (str(job_id),)
        ).fetchone()
        return None if row is None else Job(row)

    def get_from_pid(self, pid: int) -> Job | None:
        row = self.conn.execute("SELECT * FROM jobs WHERE pid=?", (pid,)).fetchone()
        return None if row is None else Job(row)

    def update(self, job_id: int, status) -> Job | None:
        with contextlib.suppress(sqlite3.Error):
            self.conn.execute(
                "UPDATE jobs SET status=?, last_update=? WHERE id=?",
                (str(status), str(int(time.monotonic())), str(job_id)),
            )
            self.conn.commit()
            return self.get(job_id)
        return None

    def delete(self, job_id: int) -> None:
        with contextlib.suppress(sqlite3.Error):
            self.conn.execute("DELETE FROM jobs WHERE id=?", (str(job_id),))
            self.conn.commit()

    def all_ids(self) -> list[int]:
        jobs = self.conn.execute("SELECT * FROM jobs")
        return [job["id"] for job in jobs]

    def running(self) -> Iterator[Job]:
        jobs = self.conn.execute(
            "SELECT * FROM jobs WHERE status=?", (str(Job.RUNNING),)
        )
        for job in jobs:
            yield Job(job)

    def canceling(self) -> Iterator[Job]:
        jobs = self.conn.execute(
            "SELECT * FROM jobs WHERE status=?", (str(Job.CANCELING),)
        )
        for job in jobs:
            yield Job(job)

    def finished(self) -> Iterator[Job]:
        jobs = self.conn.execute(
            "SELECT * FROM jobs WHERE status=?", (str(Job.FINISHED),)
        )
        for job in jobs:
            yield Job(job)


##########
# Setups #
##########
def setup_logger(log_file: str, level: str) -> None:
    """
    Configure the logger

    :param log_file: the log_file or "-" for sys.stdout
    :param level: the log level
    """
    # Configure the log handler
    if log_file == "-":
        handler: logging.Handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.handlers.WatchedFileHandler(log_file)
    handler.setFormatter(logging.Formatter(FORMAT))
    LOG.addHandler(handler)

    # Set-up the LOG level
    if level == "ERROR":
        LOG.setLevel(logging.ERROR)
    elif level == "WARN":
        LOG.setLevel(logging.WARN)
    elif level == "INFO":
        LOG.setLevel(logging.INFO)
    else:
        LOG.setLevel(logging.DEBUG)


#####################
# Server <-> Worker #
#####################
def cancel(url: str, jobs: JobsDB, job_id: int, token: str) -> None:
    LOG.info("[%d] => CANCEL", job_id)
    job = jobs.get(job_id)
    if job is None:
        LOG.debug("[%d] Unknown job", job_id)
        job = jobs.create(job_id, 0, Job.FINISHED, "", token)
    else:
        if job.status == Job.RUNNING and job.is_running():
            LOG.debug("[%d] Canceling", job_id)
            job.terminate()
            jobs.update(job_id, Job.CANCELING)


async def finish_job(
    session: aiohttp.ClientSession, url: str, job: Job, jobs: JobsDB
) -> None:
    LOG.info("[%d] FINISHED => server", job.job_id)
    result = job.result()
    # Default error values
    if result.get("result") == "pass":
        default_error_type = ""
    else:
        default_error_type = LAVABug.error_type
    data = {
        "state": "FINISHED",
        "result": result.get("result", "fail"),
        "error_type": result.get("error_type", default_error_type),
        "errors": job.errors(),
        "description": job.description(),
    }

    ret = await aiohttp_post(
        session, f"{url}{URL_JOBS}{job.job_id}/", job.token, data=data
    )
    if ret.status_code != 200:
        LOG.error("[%d] -> server error: code %d", job.job_id, ret.status_code)
        LOG.debug("[%d] --> %s", job.job_id, ret.text)
        if ret.status_code != 404:  # If the job is not present on lava-server delete it
            return

    # Remove stale resources
    prefix = "" if job is None else job.prefix
    cleanup_task = asyncio.get_running_loop().create_task(
        cleanup_job(prefix, job.job_id)
    )
    JOB_ASYNC_TASKS.add(cleanup_task)
    cleanup_task.add_done_callback(JOB_ASYNC_TASKS.discard)

    jobs.delete(job.job_id)


async def check(session: aiohttp.ClientSession, url: str, jobs: JobsDB) -> None:
    # Loop on running jobs
    for job in jobs.running():
        if not job.is_running():
            # wait for the job
            try:
                os.waitpid(job.pid, os.WNOHANG)
            except OSError as exc:
                LOG.debug(
                    "[%d] unable to wait for the process: %s", job.job_id, str(exc)
                )
            LOG.info("[%d] running -> finished", job.job_id)
            jobs.update(job.job_id, Job.FINISHED)

    # Loop on canceling jobs
    for job in jobs.canceling():
        if not job.is_running():
            # wait for the job
            try:
                os.waitpid(job.pid, os.WNOHANG)
            except OSError as exc:
                LOG.debug(
                    "[%d] unable to wait for the process: %s", job.job_id, str(exc)
                )
            LOG.info("[%d] canceling -> finished", job.job_id)
            jobs.update(job.job_id, Job.FINISHED)

        elif time.monotonic() - job.last_update > FINISH_MAX_DURATION:
            LOG.info("[%d] not finishing => killing", job.job_id)
            job.kill()
        elif time.monotonic() - job.last_update > FINISH_MAX_DURATION / 2:
            LOG.info("[%d] not finishing => second signal", job.job_id)
            job.terminate()

    # Loop on finished jobs
    for job in jobs.finished():
        await finish_job(session, url, job, jobs)


class ServerUnavailable(Exception):
    def __init__(self, message):
        super().__init__(message)
        sentry_sdk.capture_exception(self)


class VersionMismatch(Exception):
    pass


async def ping(
    session: aiohttp.ClientSession, url: str, token: str, name: str
) -> dict[str, list]:
    LOG.debug("PING => server")
    ret = await aiohttp_get(
        session, f"{url}{URL_WORKERS}{name}/", token, params={"version": __version__}
    )
    if ret.status_code != 200:
        LOG.error("-> server error: code %d", ret.status_code)
        LOG.debug("--> %s", ret.text)
        if ret.status_code // 100 == 5:
            raise ServerUnavailable(ret.text)
        if ret.status_code == 409:
            raise VersionMismatch(ret.text)
        return {}

    try:
        return ret.json()
    except ValueError as exc:
        LOG.error("-> invalid response: %r", str(exc))
        return {}


async def register(
    session: aiohttp.ClientSession,
    url: str,
    name: str,
    username: str | None = None,
    password: str | None = None,
) -> str:
    data = {"name": name}
    if username is not None and password is not None:
        data["username"] = username
        data["password"] = password

    while True:
        LOG.debug("[INIT] Auto register as %r", name)
        ret = await aiohttp_post(session, f"{url}{URL_WORKERS}", None, data=data)
        if ret.status_code == 200:
            return ret.json()["token"]
        LOG.error("[INIT] -> server error: code %d", ret.status_code)
        LOG.debug("[INIT] --> %s", ret.text)
        await asyncio.sleep(5)


async def running(
    session: aiohttp.ClientSession,
    url: str,
    jobs: JobsDB,
    job_id: int,
    token: str,
    job_log_interval: int,
) -> None:
    job = jobs.get(job_id)
    if job is None:
        await start(session, url, jobs, job_id, token, job_log_interval)


async def start(
    session: aiohttp.ClientSession,
    url: str,
    jobs: JobsDB,
    job_id: int,
    token: str,
    job_log_interval: int,
) -> None:
    LOG.info("[%d] server => START", job_id)
    # Was the job already started?
    job = jobs.get(job_id)

    # Start the job
    if job is None:
        ret = await aiohttp_get(session, f"{url}{URL_JOBS}{job_id}/", token)
        if ret.status_code != 200:
            LOG.error("[%d] -> server error: code %d", job_id, ret.status_code)
            LOG.debug("[%d] --> %s", job_id, ret.text)
            return

        try:
            data = ret.json()
            definition = data["definition"]
            device = data["device"]
            dispatcher = data["dispatcher"]
            env = data["env"]
            env_dut = data["env-dut"]
        except (KeyError, ValueError) as exc:
            LOG.error("[%d] -> invalid response: %r", job_id, str(exc))
            return

        LOG.info("[%d] Starting job", job_id)
        LOG.debug("[%d]         : %r", job_id, definition)
        LOG.debug("[%d] device  : %r", job_id, device)
        LOG.debug("[%d] dispatch: %r", job_id, dispatcher)
        LOG.debug("[%d] env     : %r", job_id, env)
        LOG.debug("[%d] env-dut : %r", job_id, env_dut)

        # Start the job, grab the pid and create it in the dabatase
        pid = start_job(
            url,
            token,
            job_id,
            definition,
            device,
            dispatcher,
            env,
            env_dut,
            job_log_interval,
        )
        job = jobs.create(
            job_id,
            0 if pid is None else pid,
            Job.FINISHED if pid is None else Job.RUNNING,
            yaml_safe_load(dispatcher),
            token,
        )
    else:
        LOG.info("[%d] -> already running", job_id)

    # Update the server state
    LOG.info("[%d] RUNNING => server", job_id)
    ret = await aiohttp_post(
        session, f"{url}{URL_JOBS}{job_id}/", token, data={"state": "RUNNING"}
    )
    if ret.status_code != 200:
        LOG.error("[%d] -> server error: code %d", job_id, ret.status_code)
        LOG.debug("[%d] --> %s", job_id, ret.text)


###############
# Entrypoints #
###############
async def handle(options, session: aiohttp.ClientSession, jobs: JobsDB) -> None:
    name: str = options.name
    token: str = options.token
    url: str = options.url
    job_log_interval: int = options.job_log_interval

    try:
        data = await ping(session, url, token, name)
    except ServerUnavailable:
        LOG.error("-> server unavailable")
        return
    except VersionMismatch as exc:
        if options.exit_on_version_mismatch:
            raise exc
        return

    # running jobs
    for job in data.get("running", []):
        await running(session, url, jobs, job["id"], job["token"], job_log_interval)

    # cancel jobs
    for job in data.get("cancel", []):
        cancel(url, jobs, job["id"], job["token"])

    # start jobs
    for job in data.get("start", []):
        await start(session, url, jobs, job["id"], job["token"], job_log_interval)

    # Check job status
    # TODO: store the token and reuse it
    await check(session, url, jobs)


async def main_loop(
    options, session: aiohttp.ClientSession, jobs: JobsDB, event: asyncio.Event
) -> None:
    loop = asyncio.get_running_loop()
    while True:
        timer_handle = loop.call_later(ping_interval, event.set)
        try:
            async with jobs.lock:
                await handle(options, session, jobs)
            await event.wait()
        finally:
            timer_handle.cancel()
            event.clear()


async def sigchild_handler_async(
    session: aiohttp.ClientSession, url: str, jobs: JobsDB
) -> None:
    async with jobs.lock:
        jobs_to_finish: list[Job] = []
        with contextlib.suppress(ChildProcessError):
            while (waitpid_tuple := os.waitpid(-1, os.WNOHANG)) != (0, 0):
                pid, exit_code = waitpid_tuple
                LOG.debug(
                    "Collected PID %d with exit code %d from SIGCHLD", pid, exit_code
                )

                job = jobs.get_from_pid(pid)
                if job is not None:
                    jobs_to_finish.append(job)
                else:
                    LOG.debug("Unknown PID collected %d from SIGCHLD", pid)

        results = await asyncio.gather(
            *(finish_job(session, url, job, jobs) for job in jobs_to_finish),
            # If a job finish fails it will remain in database
            # and later can be finished by the main loop
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, BaseException):
                LOG.exception("Exception raised during SIGCHLD job finish", exc_info=r)


def sigchld_handler(session: aiohttp.ClientSession, url: str, jobs: JobsDB) -> None:
    handler_task = asyncio.get_running_loop().create_task(
        sigchild_handler_async(session, url, jobs)
    )
    JOB_ASYNC_TASKS.add(handler_task)
    handler_task.add_done_callback(JOB_ASYNC_TASKS.discard)


async def listen_for_events(
    options, session: aiohttp.ClientSession, event: asyncio.Event
) -> None:
    retry_interval = 1
    while True:
        try:
            LOG.info("[EVENT] Connecting to websocket")
            async with session.ws_connect(
                f"{options.ws_url}",
                headers={"LAVA-Token": options.token, "LAVA-Host": options.name},
                heartbeat=30,
            ) as ws:
                retry_interval = 1
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    try:
                        data = json.loads(msg.data)
                        (topic, _, dt, username, data) = data
                        data = json.loads(data)
                    except ValueError:
                        LOG.warning("[EVENT] Invalid message: %s", msg)
                        continue
                    if not topic.endswith(".testjob"):
                        continue
                    if data.get("worker") != options.name:
                        continue
                    if data.get("state") in ["Scheduled", "Canceling"]:
                        LOG.info("[EVENT] Worker mentioned")
                        event.set()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            retry_interval = min(60, retry_interval * 2)
        await asyncio.sleep(retry_interval)


def ask_exit(signame: str, group: asyncio.Future[Any]) -> None:
    LOG.info(f"[EXIT] Received signal {signame}")
    # await cancelled group throws asyncio.CancelledError. The
    # exception is handled in the main().
    group.cancel()


async def main() -> int:
    # Parse command line
    options = get_parser().parse_args()
    if options.sentry_dsn:
        init_sentry_sdk(options.sentry_dsn)
    if options.token_file is None:
        options.token_file = Path(options.worker_dir) / "token"
    options.url = options.url.rstrip("/")
    if options.ws_url is None:
        options.ws_url = f"{options.url}/ws/"

    # Setup logger
    setup_logger(options.log_file, options.level)
    LOG.info("[INIT] LAVA worker has started.")
    LOG.info("[INIT] Name   : %r", options.name)
    LOG.info("[INIT] Server : %r", options.url)
    LOG.info("[INIT] Version: %r", __version__)

    # Set ping interval
    global ping_interval
    ping_interval = options.ping_interval
    # Setup debugging if needed
    global debug
    debug = options.debug

    # Setup timeout
    global TIMEOUT
    TIMEOUT = options.http_timeout

    worker_dir = options.worker_dir
    worker_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

    if worker_dir != WORKER_DIR:
        global tmp_dir
        tmp_dir = worker_dir / "tmp"
        # Update stale config dictionary.
        STALE_CONFIG[tmp_dir] = "{prefix}{job_id}"

    loop = asyncio.get_running_loop()
    loop.set_default_executor(THREAD_EXECUTOR)

    async with aiohttp.ClientSession(
        headers={
            "User-Agent": f"lava-worker {__version__}",
        },
        timeout=aiohttp.ClientTimeout(total=TIMEOUT),
    ) as session:
        try:
            if options.username is not None:
                LOG.info("[INIT] Token  : '<auto register with %s>'", options.username)
                password = getpass.getpass()
                options.token = await register(
                    session, options.url, options.name, options.username, password
                )
                options.token_file.write_text(options.token, encoding="utf-8")
                options.token_file.chmod(0o600)
            elif options.token is not None:
                LOG.info("[INIT] Token  : '<command line>'")
                options.token_file.write_text(options.token, encoding="utf-8")
                options.token_file.chmod(0o600)
            elif options.token_file.exists():
                LOG.info("[INIT] Token  : file %r", str(options.token_file))
                options.token = options.token_file.read_text(encoding="utf-8").rstrip(
                    "\n"
                )
            else:
                LOG.info("[INIT] Token  : '<auto register>'")
                options.token = await register(session, options.url, options.name)
                options.token_file.write_text(options.token, encoding="utf-8")
                options.token_file.chmod(0o600)

            jobs = JobsDB(str(worker_dir / "db.sqlite3"))

            event = asyncio.Event()
            group = asyncio.gather(
                main_loop(options, session, jobs, event),
                listen_for_events(options, session, event),
            )

            LOG.debug(f"LAVA worker pid is {os.getpid()}")
            for sig in (Signals.SIGINT, Signals.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    partial(ask_exit, sig.name, group),
                )

            loop.add_signal_handler(
                Signals.SIGCHLD, partial(sigchld_handler, session, options.url, jobs)
            )

            await group
            return 0
        except asyncio.CancelledError:
            LOG.info("[EXIT] Canceled")
            if options.wait_jobs:
                LOG.info("[EXIT] Wait for jobs to finish")
                while True:
                    await check(session, options.url, jobs)
                    all_ids = jobs.all_ids()
                    LOG.info(
                        "[EXIT] => %d jobs ([%s])",
                        len(all_ids),
                        ", ".join(str(i) for i in all_ids),
                    )
                    if not all_ids:
                        break
                    await asyncio.sleep(ping_interval)
            return 1
        except VersionMismatch as exc:
            LOG.info("[EXIT] %s" % exc)
            return 0
        except Exception as exc:
            LOG.error("[EXIT] %s", exc)
            LOG.exception(exc)
            return 1


def run() -> None:
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        LOG.info("[EXIT] Received Ctrl+C")
        sys.exit(1)


if __name__ == "__main__":
    run()
