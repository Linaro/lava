# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from json import dumps as json_dumps
from multiprocessing import Pipe
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs

import responses

from lava_common.constants import REQUEST_DATA_TOO_BIG_MSG
from lava_common.log import LavaLogUploader, dump
from lava_common.yaml import yaml_safe_load

LOGS_UPLOAD_URL = "http://localhost/internal/v1/jobs/12345/logs/"


def lava_logs_callback(
    request: responses.PreparedRequest,
) -> tuple[int, dict[str, str], str]:
    lines_str = parse_qs(request.body)["lines"][0]
    return 200, {}, json_dumps({"line_count": len(yaml_safe_load(lines_str))})


class TestJobLogs(TestCase):
    def setUp(self) -> None:
        self.read_pipe, self.write_pipe = Pipe(duplex=False)
        self.log_uploader = LavaLogUploader(
            conn=self.read_pipe,
            url=LOGS_UPLOAD_URL,
            token="lava-test-token",
            max_time=1,
        )

    @staticmethod
    def generate_records(number: int = LavaLogUploader.MAX_RECORDS) -> list[str]:
        return [dump({"msg": "test"})] * number

    def create_responses(self, callback=lava_logs_callback) -> responses.RequestsMock:
        rsps = responses.RequestsMock()
        rsps.add_callback(
            responses.POST,
            LOGS_UPLOAD_URL,
            callback=callback,
            content_type="application/json",
        )
        return rsps

    def test_job_logs_main_loop_max_records(self) -> None:
        num_records = self.log_uploader.MAX_RECORDS + self.log_uploader.MAX_RECORDS // 2

        for record in self.generate_records(num_records):
            self.write_pipe.send_bytes(record.encode("utf-8", errors="replace"))

        self.write_pipe.send_bytes(b"")

        with self.create_responses():
            self.log_uploader.run()

            self.assertEqual(self.log_uploader.MAX_RECORDS, self.log_uploader.index)
            self.assertTrue(self.log_uploader.records)

            self.log_uploader.close()

            self.assertEqual(num_records, self.log_uploader.index)
            self.assertFalse(self.log_uploader.records)

    def test_job_logs_uploader_simple_flush(self) -> None:
        num_records = 500
        self.log_uploader.records.extend(self.generate_records(num_records))
        with self.create_responses():
            self.log_uploader.flush()

        self.assertEqual(num_records, self.log_uploader.index)
        self.assertFalse(self.log_uploader.records)

    def test_job_logs_uploader_too_large_request(self) -> None:
        inital_records_num = LavaLogUploader.MAX_RECORDS * 4
        self.log_uploader.records.extend(self.generate_records(inital_records_num))
        num_request_records = inital_records_num

        def too_large_request_callback(
            request: responses.PreparedRequest,
        ) -> tuple[int, dict[str, str], str]:
            nonlocal num_request_records
            lines_str = parse_qs(request.body)["lines"][0]
            num_request_records = len(yaml_safe_load(lines_str))

            if num_request_records > 500:
                return 413, {}, REQUEST_DATA_TOO_BIG_MSG

            return 200, {}, json_dumps({"line_count": num_request_records})

        with self.create_responses(callback=too_large_request_callback):
            self.log_uploader.flush()

        self.assertEqual(
            len(self.log_uploader.records),
            inital_records_num - num_request_records,
        )

    def test_job_logs_exception_printer(self) -> None:
        num_records = 500
        self.log_uploader.records.extend(self.generate_records(num_records))

        class TestExceptionOne(Exception):
            # Test Exception
            ...

        class TestExceptionTwo(Exception):
            # Test Exception
            ...

        with patch("lava_common.log.stderr") as stderr_mock:
            self.assertIsNone(self.log_uploader.last_exception_type)

            with patch.object(
                self.log_uploader.session, "post", side_effect=TestExceptionOne
            ):
                self.log_uploader.flush()
                self.assertIs(self.log_uploader.last_exception_type, TestExceptionOne)
                self.assertEqual(1, stderr_mock.write.call_count)

                self.log_uploader.flush()
                self.log_uploader.flush()
                self.assertEqual(self.log_uploader.exception_counter, 2)
                self.assertEqual(1, stderr_mock.write.call_count)

            with self.create_responses():
                self.log_uploader.flush()

            self.assertEqual(2, stderr_mock.write.call_count)
            self.assertEqual(0, self.log_uploader.exception_counter)
            self.assertIsNone(self.log_uploader.last_exception_type)
