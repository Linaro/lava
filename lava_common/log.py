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
import time
from sys import stderr

import requests

from lava_common.exceptions import RequestBodyTooLargeError
from lava_common.version import __version__
from lava_common.yaml import yaml_safe_dump


def dump(data: dict) -> str:
    # Set width to a really large value in order to always get one line.
    # But keep this reasonable because the logs will be loaded by CLoader
    # that is limited to around 10**7 chars
    data_str = yaml_safe_dump(
        data, default_flow_style=True, default_style='"', width=10**6
    )[:-1]
    # Test the limit and skip if the line is too long
    if len(data_str) >= 10**6:
        if isinstance(data["msg"], str):
            data["msg"] = "<line way too long ...>"
        else:
            data["msg"] = {"skip": "line way too long ..."}
        data_str = yaml_safe_dump(
            data, default_flow_style=True, default_style='"', width=10**6
        )[:-1]
    return data_str


class LavaLogUploader:
    MAX_RECORDS = 1000
    FAILURE_SLEEP = 5

    def __init__(
        self,
        conn: multiprocessing.connection.Connection,
        url: str,
        token: str,
        max_time: int,
    ):
        self.conn = conn
        self.url = url
        self.token = token
        self.max_time = max_time

        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": f"lava {__version__}", "LAVA-Token": token}
        )

        self.last_exception_type: type[Exception] | None = None
        self.exception_counter = 0
        self.records: list[str] = []
        self.index = 0

    def close(self) -> None:
        while self.records:
            self.flush()

        self.session.close()

    def run(self) -> None:
        last_flush = time.monotonic()
        leaving = False

        while not leaving:
            # Listen for new messages if we don't have message yet or some
            # messages are already in the socket.
            if len(self.records) == 0 or self.conn.poll(self.max_time):
                data = self.conn.recv_bytes()
                if data == b"":
                    leaving = True
                else:
                    self.records.append(data.decode("utf-8", errors="replace"))

            records_limit = len(self.records) >= self.MAX_RECORDS
            time_limit = (time.monotonic() - last_flush) >= self.max_time
            if self.records and (records_limit or time_limit):
                last_flush = time.monotonic()
                # Send the data
                while self.records:
                    self.flush()

    def flush(self) -> None:
        for num_records_to_send in range(self.MAX_RECORDS, -1, -100):
            try:
                self.send_records(max(1, num_records_to_send))
                return
            except RequestBodyTooLargeError:
                # Retry with lower number of records
                ...

    def send_records(self, num_records: int) -> None:
        records_to_send = self.records[:num_records]
        try:
            ret = self.session.post(
                self.url,
                data={
                    "lines": "- " + "\n- ".join(records_to_send),
                    "index": self.index,
                },
            )
            if self.exception_counter > 0:
                now = datetime.datetime.utcnow().isoformat()
                stderr.write(f"{now}: <{self.exception_counter} skipped>\n")
                self.last_exception_type = None
                self.exception_counter = 0
        except Exception as exc:
            if self.last_exception_type == type(exc):
                self.exception_counter += 1
            else:
                now = datetime.datetime.utcnow().isoformat()
                if self.exception_counter:
                    stderr.write(f"{now}: <{self.exception_counter} skipped>\n")
                stderr.write(f"{now}: {str(exc)}\n")
                self.last_exception_type = type(exc)
                self.exception_counter = 0
                stderr.flush()

            return

        if ret.status_code == 200:
            with contextlib.suppress(KeyError, ValueError):
                count = int(ret.json()["line_count"])
                records_to_send = records_to_send[count:]
                self.index += count
        elif ret.status_code == 404:
            self.records.clear()
            os.kill(os.getppid(), signal.SIGTERM)
            return
        else:
            if ret.status_code == 413:
                raise RequestBodyTooLargeError
            # If the request fails, give some time for the server to
            # recover from the failure.
            time.sleep(self.FAILURE_SLEEP)

        self.records[:] = records_to_send + self.records[num_records:]


def run_lava_logs_uploader(
    conn: multiprocessing.connection.Connection,
    url: str,
    token: str,
    max_time: int,
) -> None:
    log_uploader = LavaLogUploader(conn, url, token, max_time)
    with contextlib.closing(log_uploader):
        log_uploader.run()


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
