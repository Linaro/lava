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
import sys
import time
from queue import Empty
from typing import TYPE_CHECKING, TypedDict

import requests

from lava_common.version import __version__
from lava_common.yaml import yaml_safe_dump

if TYPE_CHECKING:
    from typing import Any


def dump(data: dict[str, Any]) -> str:
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


class JobOutputSender:
    FAILURE_SLEEP = 5

    def __init__(
        self,
        conn: multiprocessing.Queue[str | None],
        url: str,
        token: str,
        max_time: int,
        job_id: str,
    ):
        self.conn = conn
        self.url = url
        self.token = token
        self.max_time = max_time
        self.job_id = job_id
        self.max_records = 1000

        self.headers = {"User-Agent": f"lava {__version__}", "LAVA-Token": token}
        self.session = requests.Session()
        # Record the exception to prevent spamming
        self.last_exception_type: type[Exception] | None = None
        self.exception_counter = 0
        self.last_error_code: int = 0
        self.error_counter: int = 0

        self.records: list[str] = []
        self.index = 0

    def read_and_send_records(self) -> None:
        last_call = time.monotonic()
        leaving = False
        while not leaving:
            # Listen for new messages if we don't have message yet
            if len(self.records) == 0:
                with contextlib.suppress(Empty):
                    data = self.conn.get(block=True, timeout=self.max_time)
                    if data is None:
                        leaving = True
                    else:
                        self.records.append(data)

            # Drain the queue to collect records for batch uploading
            while len(self.records) < self.max_records:
                try:
                    data = self.conn.get_nowait()
                    if data is None:
                        leaving = True
                        break
                    self.records.append(data)
                except Empty:
                    break

            records_limit = len(self.records) >= self.max_records
            time_limit = (time.monotonic() - last_call) >= self.max_time
            if self.records and (records_limit or time_limit):
                last_call = time.monotonic()
                # Send the data
                self.post()

    def run(self) -> None:
        with self.session:
            self.read_and_send_records()

            # Flush remaining records
            while self.records:
                # Send the data
                self.post()

    def record_post_result(self, ret: requests.Response) -> None:
        status_code = ret.status_code
        now = datetime.datetime.utcnow().isoformat()

        if status_code == 200:
            sys.stdout.write(
                f"{now} INFO [LOGGER] POST: total records sent: {self.index}\n"
            )
            sys.stdout.flush()
            if self.error_counter > 1:
                sys.stderr.write(
                    f"{now} ERROR [LOGGER] POST: "
                    f"<{self.error_counter} consecutive errors skipped>\n"
                )
                self.error_counter = 0
                sys.stderr.flush()
        else:
            if status_code == self.last_error_code:
                self.error_counter += 1
            else:
                if self.error_counter > 1:
                    sys.stderr.write(
                        f"{now} ERROR [LOGGER] POST: "
                        f"<{self.error_counter} consecutive errors skipped>\n"
                    )
                self.error_counter = 0
                self.last_error_code = ret.status_code
                sys.stderr.write(
                    f"{now} ERROR [LOGGER] POST: {status_code} - {ret.text} \n"
                )
                sys.stderr.flush()

    def post(self) -> None:
        # limit the number of records to send in one call
        records_to_send = self.records[: self.max_records]
        # In case of exception, print the exception to stderr that will be
        # forwarded to lava-server by lava-worker. If the same exception is
        # raised multiple time in a row, record also the number of
        # occurrences.
        try:
            ret = self.session.post(
                self.url,
                data={
                    "lines": "- " + "\n- ".join(records_to_send),
                    "index": self.index,
                },
                headers=self.headers,
                timeout=120,
            )
            if self.exception_counter > 0:
                now = datetime.datetime.utcnow().isoformat()
                sys.stderr.write(
                    f"{now} EXCEPTION [LOGGER] POST: "
                    f"<{self.exception_counter} consecutive exceptions skipped>\n"
                )
                sys.stderr.flush()
                self.last_exception_type = None
                self.exception_counter = 0
        except Exception as exc:
            if self.last_exception_type == type(exc):
                self.exception_counter += 1
            else:
                now = datetime.datetime.utcnow().isoformat()
                if self.exception_counter:
                    sys.stderr.write(
                        f"{now} EXCEPTION [LOGGER] POST: "
                        f"<{self.exception_counter} consecutive exceptions skipped>\n"
                    )
                sys.stderr.write(f"{now} EXCEPTION [LOGGER] POST: {str(exc)}\n")
                self.last_exception_type = type(exc)
                self.exception_counter = 0
                sys.stderr.flush()

            time.sleep(self.FAILURE_SLEEP)
            return

        if ret.status_code == 200:
            with contextlib.suppress(KeyError, ValueError):
                count = int(ret.json()["line_count"])
                # Discard records that were successfully sent
                self.records[0:count] = []
                self.index += count
        elif ret.status_code == 404:
            json_data = {}
            try:
                json_data = ret.json()
                if json_data.get("error") == f"Unknown job '{self.job_id}'":
                    self.records[:] = []
                    records_to_send.clear()
                    os.kill(os.getppid(), signal.SIGUSR1)
                else:
                    time.sleep(self.FAILURE_SLEEP)
            # When the 'ret.json()' fails to decode the response, requests
            # v2.25.1 on Debian 11 returns 'json.JSONDecodeError' but
            # requests >= 2.27.0 returns 'requests.exceptions.JSONDecodeError'
            # which is an invalid attribute on Debian 11. 'ValueError' is
            # used here until Debian 11 is dropped.
            except ValueError:
                time.sleep(self.FAILURE_SLEEP)
        elif ret.status_code == 413:
            self._reduce_record_size()
        else:
            # If the request fails, give some time for the server to
            # recover from the failure.
            time.sleep(self.FAILURE_SLEEP)

        self.record_post_result(ret)

    def _reduce_record_size(self) -> None:
        """
        The method should only be called for handling 413 HTTP error code. It
        minus 100 records for every call. In case only one record left, the record will
        be replaced by a short "log-upload fail" result line and an error message also
        will be sent to kill the job.
        """
        if self.max_records == 1:
            record = self.records[0]
            self.records[:] = [
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
            ]

            now = datetime.datetime.utcnow().isoformat()
            sys.stderr.write(
                f"{now} ERROR [LOGGER] POST: "
                "Log post request body exceeds server settings param.\n"
                f"Log line length: {len(record)}\n"
                f"Truncated log line: {record[:1024]} ...\n"
            )
            sys.stderr.flush()
        else:
            self.max_records = max(1, self.max_records - 100)


def run_output_sender(
    conn: multiprocessing.Queue[str | None],
    url: str,
    token: str,
    max_time: int,
    job_id: str,
) -> None:
    JobOutputSender(
        conn=conn,
        url=url,
        token=token,
        max_time=max_time,
        job_id=job_id,
    ).run()


class HTTPHandler(logging.Handler):
    def __init__(self, url: str, token: str, interval: int, job_id: str):
        super().__init__()
        self.formatter = logging.Formatter("%(message)s")
        # Create the multiprocess sender
        self.queue: multiprocessing.Queue[str | None] = multiprocessing.Queue()
        # Block sigint so the sender function will not receive it.
        # TODO: block more signals?
        signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGINT])
        self.proc = multiprocessing.Process(
            target=run_output_sender, args=(self.queue, url, token, interval, job_id)
        )
        self.proc.start()
        signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGINT])

    def emit(self, record: logging.LogRecord) -> None:
        if self.formatter is not None:
            data = self.formatter.format(record)
            # Skip empty strings
            # This can't happen as data is a dictionary dumped in yaml format
            if data == "":
                return
            self.queue.put(data)

    def close(self) -> None:
        super().close()

        # wait for the multiprocess
        self.queue.put(None)
        self.proc.join()

    def terminate(self) -> None:
        self.proc.terminate()
        self.proc.join()


class MarkerDict(TypedDict):
    case: str
    type: str


class ResultDict(TypedDict, total=False):
    definition: str
    namespace: str
    case: str
    level: str | None
    duration: str
    result: str
    extra: dict[str, Any]
    starttc: int | None
    endtc: int | None


class YAMLLogger(logging.Logger):
    def __init__(self, name: str):
        super().__init__(name)
        self.handler: HTTPHandler | None = None
        self.markers: dict[str, dict[str, int]] = {}
        self.line = 0

    def addHTTPHandler(
        self, url: str, token: str, interval: int, job_id: str
    ) -> HTTPHandler:
        self.handler = HTTPHandler(url, token, interval, job_id)
        self.addHandler(self.handler)
        return self.handler

    def close(self) -> None:
        if self.handler is not None:
            self.handler.close()
            self.removeHandler(self.handler)
            self.handler = None
        # Close other handlers
        for handler in self.handlers:
            handler.close()

    def terminate(self) -> None:
        if self.handler is not None:
            self.handler.terminate()
            self.removeHandler(self.handler)
            self.handler = None

    def log_message(
        self, level: int, level_name: str, message: object, *args: Any, **kwargs: Any
    ) -> None:
        # Increment the line count
        self.line += 1
        # Build the dictionary
        data: dict[str, Any] = {
            "dt": datetime.datetime.utcnow().isoformat(),
            "lvl": level_name,
        }

        if isinstance(message, str) and args:
            data["msg"] = message % args
        else:
            data["msg"] = message

        if level_name == "feedback" and "namespace" in kwargs:
            data["ns"] = kwargs["namespace"]

        data_str = dump(data)
        self._log(level, data_str, ())

    def exception(  # type: ignore [override]
        self, exc: object, *args: Any, **kwargs: Any
    ) -> None:
        self.log_message(logging.ERROR, "exception", exc, *args, **kwargs)

    def error(  # type: ignore [override]
        self, message: object, *args: Any, **kwargs: Any
    ) -> None:
        self.log_message(logging.ERROR, "error", message, *args, **kwargs)

    def warning(  # type: ignore [override]
        self, message: object, *args: Any, **kwargs: Any
    ) -> None:
        self.log_message(logging.WARNING, "warning", message, *args, **kwargs)

    def info(  # type: ignore [override]
        self, message: object, *args: Any, **kwargs: Any
    ) -> None:
        self.log_message(logging.INFO, "info", message, *args, **kwargs)

    def debug(  # type: ignore [override]
        self, message: object, *args: Any, **kwargs: Any
    ) -> None:
        self.log_message(logging.DEBUG, "debug", message, *args, **kwargs)

    def input(self, message: object, *args: Any, **kwargs: Any) -> None:
        self.log_message(logging.INFO, "input", message, *args, **kwargs)

    def target(self, message: object, *args: Any, **kwargs: Any) -> None:
        self.log_message(logging.INFO, "target", message, *args, **kwargs)

    def feedback(self, message: object, *args: Any, **kwargs: Any) -> None:
        self.log_message(logging.INFO, "feedback", message, *args, **kwargs)

    def event(self, message: object, *args: Any, **kwargs: Any) -> None:
        self.log_message(logging.INFO, "event", message, *args, **kwargs)

    def marker(self, message: MarkerDict, *args: Any, **kwargs: Any) -> None:
        case = message["case"]
        m_type = message["type"]
        self.markers.setdefault(case, {})[m_type] = self.line - 1

    def results(self, results: ResultDict, *args: Any, **kwargs: Any) -> None:
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


class YAMLListFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return f"- {msg}"
