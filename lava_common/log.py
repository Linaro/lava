# Copyright (C) 2014 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from typing import Dict, List, Tuple

import contextlib
import datetime
import logging
import multiprocessing
import requests
import signal
import time

from lava_common.compat import yaml_dump
from lava_common.version import __version__


def dump(data: Dict) -> str:
    # Set width to a really large value in order to always get one line.
    # But keep this reasonable because the logs will be loaded by CLoader
    # that is limited to around 10**7 chars
    data_str = yaml_dump(
        data, default_flow_style=True, default_style='"', width=10 ** 6
    )[:-1]
    # Test the limit and skip if the line is too long
    if len(data_str) >= 10 ** 6:
        if isinstance(data["msg"], str):
            data["msg"] = "<line way too long ...>"
        else:
            data["msg"] = {"skip": "line way too long ..."}
        data_str = yaml_dump(
            data, default_flow_style=True, default_style='"', width=10 ** 6
        )[:-1]
    return data_str


def sender(conn, url: str, token: str) -> None:
    HEADERS = {"User-Agent": f"lava {__version__}", "LAVA-Token": token}
    MAX_RECORDS = 1000
    MAX_TIME = 1

    def post(session, records: List[str], index: int) -> Tuple[List[str], int]:
        # limit the number of records to send in one call
        data, remaining = records[:MAX_RECORDS], records[MAX_RECORDS:]
        with contextlib.suppress(requests.RequestException):
            # Do not specify a timeout so we wait forever for an answer. This is a
            # background process so waiting is not an issue.
            # Will avoid resending the same request a second time if gunicorn
            # is too slow to answer.
            ret = session.post(
                url,
                data={"lines": "- " + "\n- ".join(data), "index": index},
                headers=HEADERS,
            )

            if ret.status_code == 200:
                with contextlib.suppress(KeyError, ValueError):
                    count = int(ret.json()["line_count"])
                    data = data[count:]
                    index += count
        return (data + remaining, index)

    last_call = time.time()
    records: List[str] = []
    leaving: bool = False
    index: int = 0

    with requests.Session() as session:
        while not leaving:
            # Listen for new messages if we don't have  message yet or some
            # messages are already in the socket.
            if len(records) == 0 or conn.poll(MAX_TIME):
                data = conn.recv_bytes()
                if data == b"":
                    leaving = True
                else:
                    records.append(data.decode("utf-8"))

            records_limit = len(records) >= MAX_RECORDS
            time_limit = (time.time() - last_call) >= MAX_TIME
            if records and (records_limit or time_limit):
                last_call = time.time()
                # Send the data
                (records, index) = post(session, records, index)

        while records:
            # Send the data
            (records, index) = post(session, records, index)


class HTTPHandler(logging.Handler):
    def __init__(self, url, token):
        super().__init__()
        self.formatter = logging.Formatter("%(message)s")
        # Create the multiprocess sender
        (reader, writter) = multiprocessing.Pipe(duplex=False)
        self.writter = writter
        # Block sigint so the sender function will not receive it.
        # TODO: block more signals?
        signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGINT])
        self.proc = multiprocessing.Process(target=sender, args=(reader, url, token))
        self.proc.start()
        signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGINT])

    def emit(self, record):
        data = self.formatter.format(record)
        # Skip empty strings
        # This can't happen as data is a dictionary dumped in yaml format
        if data == "":
            return
        self.writter.send_bytes(data.encode("utf-8"))

    def close(self):
        super().close()

        # wait for the multiprocess
        self.writter.send_bytes(b"")
        self.proc.join()


class YAMLLogger(logging.Logger):
    def __init__(self, name):
        super().__init__(name)
        self.handler = None
        self.markers = {}
        self.line = 0

    def addHTTPHandler(self, url, token):
        self.handler = HTTPHandler(url, token)
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
