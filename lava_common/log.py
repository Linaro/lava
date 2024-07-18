# Copyright (C) 2014 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import contextlib
import datetime
import logging
import multiprocessing
import os
import signal
from asyncio import Event, get_running_loop
from asyncio import run as asyncio_run
from asyncio import sleep
from collections import deque
from fcntl import F_SETFL, fcntl
from json import JSONDecodeError
from json import loads as json_loads
from sys import stderr
from typing import TYPE_CHECKING

from aiohttp.client import ClientSession

from lava_common.version import __version__
from lava_common.yaml import yaml_safe_dump

if TYPE_CHECKING:
    from asyncio import Future, Task
    from collections.abc import Iterator
    from typing import Any


def dump(data: dict) -> str:
    # Set width to a really large value in order to always get one line.
    # But keep this reasonable because the logs will be loaded by CLoader
    # that is limited to around 10**7 chars
    data_str = yaml_safe_dump(
        data, default_flow_style=True, default_style='"', width=10**5
    )[:-1]
    # Test the limit and skip if the line is too long
    if len(data_str) >= 10**5:
        if isinstance(data["msg"], str):
            data["msg"] = "<line way too long ...>"
        else:
            data["msg"] = {"skip": "line way too long ..."}
        data_str = yaml_safe_dump(
            data, default_flow_style=True, default_style='"', width=10**6
        )[:-1]
    return data_str


class LavaLogUploaderAsync:
    MAX_RECORDS = 1000
    FAILURE_SLEEP = 5

    def __init__(
        self,
        conn: multiprocessing.connection.Connection,
        url: str,
        token: str,
        max_time: int,
    ):
        loop = get_running_loop()

        self.conn = conn
        self.url = url
        self.token = token
        self.max_time = max_time

        self.last_exception_type: type[Exception] | None = None
        self.exception_counter = 0
        self.records: deque[str] = deque(maxlen=30_000)
        self.index = 0
        self.flush_event = Event()
        self.finish_future: Future[None] = loop.create_future()
        self.exit_stack = contextlib.AsyncExitStack()

        self.aio_http_session = ClientSession(
            headers={"User-Agent": f"lava {__version__}", "LAVA-Token": token}
        )

        # Set pipe file descriptor as non-blocking
        fcntl(conn.fileno(), F_SETFL, os.O_NONBLOCK)

    def stop(self) -> None:
        get_running_loop().remove_reader(self.conn.fileno())
        self.finish_future.set_exception(SystemExit(0))

    def read_logs(self) -> None:
        try:
            while True:
                data = self.conn.recv_bytes()
                if data == b"":
                    self.stop()
                    return

                self.records.append(data.decode("utf-8", errors="replace"))
        except BlockingIOError:
            if len(self.records) >= self.MAX_RECORDS:
                self.flush_event.set()

            return
        except EOFError:
            self.stop()

    async def run(self) -> None:
        loop = get_running_loop()
        async with self.exit_stack:
            await self.exit_stack.enter_async_context(self.aio_http_session)
            self.exit_stack.push_async_callback(self.flush_all)
            loop.add_reader(self.conn.fileno(), self.read_logs)
            flush_task: Task[None] = loop.create_task(self.flush_loop())
            self.exit_stack.callback(flush_task.cancel)

            await self.finish_future

    async def flush_all(self) -> None:
        while self.records:
            await self.flush()

    async def flush_loop(self) -> None:
        loop = get_running_loop()
        while not self.finish_future.done():
            timer_handle = loop.call_later(self.max_time, self.flush_event.set)
            await self.flush_event.wait()
            timer_handle.cancel()
            self.flush_event.clear()

            await self.flush()

    async def flush(self) -> None:
        records_to_send: list[str] = []
        for _ in range(self.MAX_RECORDS):
            try:
                records_to_send.append(self.records.popleft())
            except IndexError:
                break

        if records_to_send:
            await self.send_records(records_to_send)

    async def send_records(self, records: list[str]) -> None:
        retries = 5  # 5 attempts to send logs
        while retries >= 0:
            retries -= 1
            with self.log_request_exceptions():
                status_code, text = await self.make_post_request(
                    {
                        "lines": "- " + "\n- ".join(records),
                        "index": self.index,
                    }
                )
                if status_code == 200:
                    with contextlib.suppress(KeyError, ValueError, JSONDecodeError):
                        count = int(json_loads(text)["line_count"])
                        self.records.extendleft(records[count:])
                        self.index += count
                    return
                elif status_code == 404:
                    self.records.clear()
                    os.kill(os.getppid(), signal.SIGTERM)
                    return
                elif status_code == 413:
                    current_num_records = len(records)
                    if current_num_records <= 1:
                        # Give up
                        try:
                            self.extra_large_record(records[0])
                        except IndexError:
                            ...
                        return
                    else:
                        current_num_records = current_num_records // 2
                        retries += 1

                    records, records_to_save = (
                        records[:current_num_records],
                        records[current_num_records:],
                    )
                    self.records.extendleft(records_to_save)
                    continue

            # If the request fails, give some time for the server to
            # recover from the failure.
            await sleep(self.FAILURE_SLEEP)

    async def make_post_request(self, data: Any) -> tuple[int, str]:
        async with self.aio_http_session.post(
            self.url,
            data=data,
        ) as resp:
            return resp.status, await resp.text()

    @contextlib.contextmanager
    def log_request_exceptions(self) -> Iterator[None]:
        try:
            yield
        except Exception as exc:
            if self.last_exception_type == type(exc):
                self.exception_counter += 1
            else:
                now = datetime.datetime.utcnow().isoformat()
                if self.exception_counter:
                    print(
                        f"{now}: <{self.exception_counter} skipped>",
                        file=stderr,
                        flush=True,
                    )
                print(f"{now}: {str(exc)}", file=stderr, flush=True)
                self.last_exception_type = type(exc)
                self.exception_counter = 0

            return

        if self.exception_counter > 0:
            now = datetime.datetime.utcnow().isoformat()
            print(f"{now}: <{self.exception_counter} skipped>", file=stderr, flush=True)
            self.last_exception_type = None
            self.exception_counter = 0

    def extra_large_record(self, record: str):
        self.records.appendleft(
            dump(
                {
                    "dt": datetime.datetime.utcnow().isoformat(),
                    "lvl": "results",
                    "msg": {
                        "definition": "lava",
                        "case": "log-upload",
                        "result": "fail",
                    },
                }
            )
        )
        print(
            "Error: Log post request body exceeds server settings param.\n"
            f"Log line length: {len(record)}\n"
            f"Truncated log line: {record[:1024]} ...",
            file=stderr,
            flush=True,
        )


def run_lava_logs_uploader(
    conn: multiprocessing.connection.Connection,
    url: str,
    token: str,
    max_time: int,
) -> None:
    async def run() -> None:
        await LavaLogUploaderAsync(conn, url, token, max_time).run()

    asyncio_run(run())


class HTTPHandler(logging.Handler):
    def __init__(self, url, token, interval):
        super().__init__()
        self.formatter = logging.Formatter("%(message)s")
        # Create the multiprocess sender
        (reader, writer) = multiprocessing.Pipe(duplex=False)
        self.writer = writer
        # Block sigint so the sender function will not receive it.
        # TODO: block more signals?
        signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGINT])
        self.proc = multiprocessing.Process(
            target=run_lava_logs_uploader, args=(reader, url, token, interval)
        )
        self.proc.start()
        signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGINT])

    def emit(self, record):
        data = self.formatter.format(record)
        # Skip empty strings
        # This can't happen as data is a dictionary dumped in yaml format
        if data == "":
            return
        self.writer.send_bytes(data.encode("utf-8", errors="replace"))

    def close(self):
        super().close()

        # wait for the multiprocess
        self.writer.send_bytes(b"")
        self.proc.join()


class YAMLLogger(logging.Logger):
    def __init__(self, name):
        super().__init__(name)
        self.handler = None
        self.markers = {}
        self.line = 0

    def addHTTPHandler(self, url, token, interval):
        self.handler = HTTPHandler(url, token, interval)
        self.addHandler(self.handler)
        return self.handler

    def close(self):
        if self.handler is not None:
            self.handler.close()
            self.removeHandler(self.handler)
            self.handler = None

    def log_message(self, level, level_name, message, *args, **kwargs):
        # Increment the line count
        self.line += 1
        # Build the dictionary
        data = {"dt": datetime.datetime.utcnow().isoformat(), "lvl": level_name}

        if isinstance(message, str) and args:
            data["msg"] = message % args
        else:
            data["msg"] = message

        if level_name == "feedback" and "namespace" in kwargs:
            data["ns"] = kwargs["namespace"]

        data_str = dump(data)
        self._log(level, data_str, ())

    def exception(self, exc, *args, **kwargs):
        self.log_message(logging.ERROR, "exception", exc, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self.log_message(logging.ERROR, "error", message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self.log_message(logging.WARNING, "warning", message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self.log_message(logging.INFO, "info", message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        self.log_message(logging.DEBUG, "debug", message, *args, **kwargs)

    def input(self, message, *args, **kwargs):
        self.log_message(logging.INFO, "input", message, *args, **kwargs)

    def target(self, message, *args, **kwargs):
        self.log_message(logging.INFO, "target", message, *args, **kwargs)

    def feedback(self, message, *args, **kwargs):
        self.log_message(logging.INFO, "feedback", message, *args, **kwargs)

    def event(self, message, *args, **kwargs):
        self.log_message(logging.INFO, "event", message, *args, **kwargs)

    def marker(self, message, *args, **kwargs):
        case = message["case"]
        m_type = message["type"]
        self.markers.setdefault(case, {})[m_type] = self.line - 1

    def results(self, results, *args, **kwargs):
        if "extra" in results and "level" not in results:
            raise Exception("'level' is mandatory when 'extra' is used")

        # Extract and append test case markers
        case = results["case"]
        markers = self.markers.get(case)
        if markers is not None:
            test_case = markers.get("test_case")
            results["starttc"] = markers.get("start_test_case", test_case)
            results["endtc"] = markers.get("end_test_case", test_case)
            del self.markers[case]

        self.log_message(logging.INFO, "results", results, *args, **kwargs)
