# Copyright (C) 2014 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import datetime
import logging
import multiprocessing
import os
import signal
import sys
import time

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


def sender(conn, url: str, token: str, max_time: int) -> None:
    HEADERS = {"User-Agent": f"lava {__version__}", "LAVA-Token": token}
    MAX_RECORDS = 1000
    FAILURE_SLEEP = 5
    # Record the exception to prevent spamming
    last_exception_type = None
    exception_counter = 0

    def post(session, records: list[str], index: int) -> tuple[list[str], int]:
        nonlocal last_exception_type
        nonlocal exception_counter

        # limit the number of records to send in one call
        data, remaining = records[:MAX_RECORDS], records[MAX_RECORDS:]
        with contextlib.suppress(requests.RequestException):
            # Do not specify a timeout so we wait forever for an answer. This is a
            # background process so waiting is not an issue.
            # Will avoid resending the same request a second time if gunicorn
            # is too slow to answer.
            # In case of exception, print the exception to stderr that will be
            # forwarded to lava-server by lava-worker. If the same exception is
            # raised multiple time in a row, record also the number of
            # occurrences.
            try:
                ret = session.post(
                    url,
                    data={"lines": "- " + "\n- ".join(data), "index": index},
                    headers=HEADERS,
                )
                if exception_counter > 0:
                    now = datetime.datetime.utcnow().isoformat()
                    sys.stderr.write(f"{now}: <{exception_counter} skipped>\n")
                    last_exception_type = None
                    exception_counter = 0
            except Exception as exc:
                if last_exception_type == type(exc):
                    exception_counter += 1
                else:
                    now = datetime.datetime.utcnow().isoformat()
                    if exception_counter:
                        sys.stderr.write(f"{now}: <{exception_counter} skipped>\n")
                    sys.stderr.write(f"{now}: {str(exc)}\n")
                    last_exception_type = type(exc)
                    exception_counter = 0
                    sys.stderr.flush()

                # Empty response for the rest of the code
                ret = requests.models.Response()

            if ret.status_code == 200:
                with contextlib.suppress(KeyError, ValueError):
                    count = int(ret.json()["line_count"])
                    data = data[count:]
                    index += count
            elif ret.status_code == 404:
                data, remaining = [], []
                os.kill(os.getppid(), signal.SIGTERM)
            else:
                if ret.status_code == 413:
                    raise RequestBodyTooLargeError
                # If the request fails, give some time for the server to
                # recover from the failure.
                time.sleep(FAILURE_SLEEP)
        return (data + remaining, index)

    last_call = time.monotonic()
    records: list[str] = []
    leaving: bool = False
    index: int = 0

    with requests.Session() as session:
        while not leaving:
            # Listen for new messages if we don't have message yet or some
            # messages are already in the socket.
            if len(records) == 0 or conn.poll(max_time):
                data = conn.recv_bytes()
                if data == b"":
                    leaving = True
                else:
                    records.append(data.decode("utf-8", errors="replace"))

            records_limit = len(records) >= MAX_RECORDS
            time_limit = (time.monotonic() - last_call) >= max_time
            if records and (records_limit or time_limit):
                last_call = time.monotonic()
                # Send the data
                try:
                    (records, index) = post(session, records, index)
                except RequestBodyTooLargeError:
                    MAX_RECORDS = max(1, MAX_RECORDS - 100)

        while records:
            # Send the data
            try:
                (records, index) = post(session, records, index)
            except RequestBodyTooLargeError:
                MAX_RECORDS = max(1, MAX_RECORDS - 100)


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
            target=sender, args=(reader, url, token, interval)
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
