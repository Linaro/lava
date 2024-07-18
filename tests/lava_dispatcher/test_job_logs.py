# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from json import dumps as json_dumps
from multiprocessing import Pipe
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from lava_common.constants import REQUEST_DATA_TOO_BIG_MSG
from lava_common.log import LavaLogUploaderAsync, dump
from lava_common.yaml import yaml_safe_load

LOGS_UPLOAD_URL = "http://localhost/internal/v1/jobs/12345/logs/"


async def lava_logs_callback_async(
    self: LavaLogUploaderAsync, data: Any
) -> tuple[int, str]:
    lines_str = data["lines"]
    return 200, json_dumps({"line_count": len(yaml_safe_load(lines_str))})


class TestJobLogsAsync(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.read_pipe, self.write_pipe = Pipe(duplex=False)
        self.log_uploader = LavaLogUploaderAsync(
            conn=self.read_pipe,
            url=LOGS_UPLOAD_URL,
            token="lava-test-token",
            max_time=1,
        )
        self.addAsyncCleanup(self.log_uploader.aio_http_session.close)

    @staticmethod
    def generate_records(number: int = LavaLogUploaderAsync.MAX_RECORDS) -> list[str]:
        return [dump({"msg": "test"})] * number

    @patch.object(LavaLogUploaderAsync, "make_post_request", lava_logs_callback_async)
    async def test_job_logs_uploader_simple_flush(self) -> None:
        num_records = 500
        self.log_uploader.records.extend(self.generate_records(num_records))

        await self.log_uploader.flush()

        self.assertEqual(num_records, self.log_uploader.index)
        self.assertFalse(self.log_uploader.records)

    async def test_job_logs_uploader_partial_flush(self) -> None:
        num_records = 500
        self.log_uploader.records.extend(self.generate_records(num_records))

        async def partial_upload_callback(
            self: LavaLogUploaderAsync,
            data: Any,
        ) -> tuple[int, str]:
            lines_str = data["lines"]
            return 200, json_dumps({"line_count": len(yaml_safe_load(lines_str)) // 2})

        with patch.object(
            LavaLogUploaderAsync,
            "make_post_request",
            partial_upload_callback,
        ):
            await self.log_uploader.flush()

        self.assertEqual(num_records // 2, self.log_uploader.index)
        self.assertEqual(len(self.log_uploader.records), num_records // 2)

    @patch.object(LavaLogUploaderAsync, "make_post_request", lava_logs_callback_async)
    async def test_job_logs_main_loop_max_records(self) -> None:
        num_records = self.log_uploader.MAX_RECORDS + self.log_uploader.MAX_RECORDS // 2

        for record in self.generate_records(num_records):
            self.write_pipe.send_bytes(record.encode("utf-8", errors="replace"))

        self.write_pipe.send_bytes(b"")

        try:
            await self.log_uploader.run()
        except SystemExit:
            ...

        self.assertEqual(num_records, self.log_uploader.index)
        self.assertFalse(self.log_uploader.records)

    async def test_job_logs_uploader_too_large_request(self) -> None:
        inital_records_num = LavaLogUploaderAsync.MAX_RECORDS * 4
        self.log_uploader.records.extend(self.generate_records(inital_records_num))
        num_request_records = inital_records_num

        num_of_requests = 0

        async def too_large_request_callback(
            self: LavaLogUploaderAsync,
            data: Any,
        ) -> tuple[int, str]:
            nonlocal num_request_records
            nonlocal num_of_requests
            lines_str = data["lines"]
            num_request_records = len(yaml_safe_load(lines_str))

            if num_request_records > 500:
                return 413, REQUEST_DATA_TOO_BIG_MSG

            num_of_requests += 1
            return 200, json_dumps({"line_count": num_request_records})

        with patch.object(
            LavaLogUploaderAsync,
            "make_post_request",
            too_large_request_callback,
        ):
            await self.log_uploader.flush()

        self.assertEqual(
            len(self.log_uploader.records),
            inital_records_num - num_request_records,
        )

    async def test_job_logs_exception_printer(self) -> None:
        num_records = 500
        self.log_uploader.records.extend(self.generate_records(num_records))

        class TestExceptionOne(Exception):
            # Test Exception
            ...

        with patch("lava_common.log.stderr") as stderr_mock, patch.object(
            LavaLogUploaderAsync,
            "FAILURE_SLEEP",
            0,
        ):
            self.assertIsNone(self.log_uploader.last_exception_type)

            with patch.object(
                LavaLogUploaderAsync,
                "make_post_request",
                side_effect=TestExceptionOne,
            ):
                await self.log_uploader.flush()
                self.assertIs(self.log_uploader.last_exception_type, TestExceptionOne)
                self.assertEqual(5, self.log_uploader.exception_counter)

            self.log_uploader.records.extend(self.generate_records(num_records))

            with patch.object(
                LavaLogUploaderAsync,
                "make_post_request",
                lava_logs_callback_async,
            ):
                await self.log_uploader.flush()

            self.assertEqual(
                4,  # 2 lines + 2 new lines
                stderr_mock.write.call_count,
            )
            self.assertEqual(0, self.log_uploader.exception_counter)
            self.assertIsNone(self.log_uploader.last_exception_type)
