# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from lava_common.exceptions import ConnectionClosedError
from lava_dispatcher.actions.test.monitor import TestMonitorAction
from lava_dispatcher.actions.test_strategy import TestMonitor
from tests.utils import RecordingLogger

from ...test_basic import LavaDispatcherTestCase


class TestMonitorAccepts(LavaDispatcherTestCase):
    def test_accepts(self):
        self.assertEqual(
            TestMonitor.accepts(None, {}),
            (False, '"monitors" not in parameters'),
        )
        self.assertEqual(
            TestMonitor.accepts(None, {"monitors": {}}),
            (True, "accepted"),
        )

        # Missing some parameters
        self.assertEqual(
            TestMonitor.accepts(
                None,
                {
                    "monitors": [
                        {
                            "start": "BOOTING ZEPHYR",
                            "end": "PROJECT EXECUTION SUCCESSFUL",
                            "pattern": (
                                "(?P<test_case_id>.*) (?P<measurement>.*) "
                                "tcs = [0-9]* nsec"
                            ),
                            "fixupdict": {"PASS": "pass", "FAIL": "fail"},
                        }
                    ]
                },
            ),
            (False, "missing required parameter 'name'"),
        )

        # Working example
        self.assertEqual(
            TestMonitor.accepts(
                None,
                {
                    "monitors": [
                        {
                            "name": "tests",
                            "start": "BOOTING ZEPHYR",
                            "end": "PROJECT EXECUTION SUCCESSFUL",
                            "pattern": (
                                "(?P<test_case_id>.*) (?P<measurement>.*) "
                                "tcs = [0-9]* nsec"
                            ),
                            "fixupdict": {"PASS": "pass", "FAIL": "fail"},
                        },
                        {
                            "name": "tests",
                            "start": "Running test suite common_test",
                            "end": "PROJECT EXECUTION SUCCESSFUL",
                            "pattern": (
                                "(?P<result>(PASS|FAIL)) - " "(?P<test_case_id>.*)\\."
                            ),
                            "fixupdict": {"PASS: pass", "FAIL,: ,fail"},
                        },
                    ]
                },
            ),
            (True, "accepted"),
        )


class Mockmatch:
    def __init__(self, data):
        self.data = data

    def groupdict(self):
        return self.data


class MockConnection:
    def __init__(self, data):
        self.match = Mockmatch(data)


class TestMonitorPatterns(LavaDispatcherTestCase):
    def test_check_patterns(self):
        job = self.create_simple_job()
        # "eof"
        action = TestMonitorAction(job)
        action.logger = RecordingLogger()
        with self.assertRaises(ConnectionClosedError):
            self.assertFalse(action.check_patterns("eof", None))
        self.assertEqual(
            action.logger.logs,
            [("warning", "err: lava test monitoring reached end of file", {})],
        )
        self.assertEqual(action.errors, ["lava test monitoring reached end of file"])

        # "timeout"
        action = TestMonitorAction(job)
        action.logger = RecordingLogger()
        self.assertFalse(action.check_patterns("timeout", None))
        self.assertEqual(
            action.logger.logs,
            [("warning", "err: lava test monitoring has timed out", {})],
        )
        self.assertEqual(action.errors, ["lava test monitoring has timed out"])

        # "end"
        action = TestMonitorAction(job)
        action.logger = RecordingLogger()
        self.assertFalse(action.check_patterns("end", None))
        self.assertEqual(
            action.logger.logs,
            [("info", "ok: end string found, lava test monitoring stopped", {})],
        )
        self.assertEqual(action.errors, [])

        # "test_result"
        action = TestMonitorAction(job)
        action.test_suite_name = "monitor-1"
        action.logger = RecordingLogger()
        action.level = "3.1"
        data = {"result": "pass", "test_case_id": "hello world"}
        self.assertTrue(action.check_patterns("test_result", MockConnection(data)))
        self.assertEqual(
            action.logger.logs,
            [
                ("info", "ok: test case found", {}),
                ("debug", "test_case_id: %s", "hello_world", {}),
                (
                    "results",
                    {
                        "definition": "monitor-1",
                        "case": "hello_world",
                        "level": "3.1",
                        "result": "pass",
                    },
                    {},
                ),
            ],
        )

        # "test_result" with "measurement" and "units"
        action = TestMonitorAction(job)
        action.test_suite_name = "monitor-1"
        action.logger = RecordingLogger()
        action.level = "3.1"
        data = {
            "result": "pass",
            "test_case_id": "hello world",
            "measurement": 1.3,
            "units": "s",
        }
        self.assertTrue(action.check_patterns("test_result", MockConnection(data)))
        self.assertEqual(
            action.logger.logs,
            [
                ("info", "ok: test case found", {}),
                ("debug", "test_case_id: %s", "hello_world", {}),
                (
                    "results",
                    {
                        "definition": "monitor-1",
                        "case": "hello_world",
                        "level": "3.1",
                        "result": "pass",
                        "measurement": 1.3,
                        "units": "s",
                    },
                    {},
                ),
            ],
        )

        # "test_result" with fixupdict
        action = TestMonitorAction(job)
        action.test_suite_name = "monitor-1"
        action.logger = RecordingLogger()
        action.level = "3.1"
        action.fixupdict = {"PASS": "pass"}
        data = {"result": "PASS", "test_case_id": "hello world"}
        self.assertTrue(action.check_patterns("test_result", MockConnection(data)))
        self.assertEqual(
            action.logger.logs,
            [
                ("info", "ok: test case found", {}),
                ("debug", "test_case_id: %s", "hello_world", {}),
                (
                    "results",
                    {
                        "definition": "monitor-1",
                        "case": "hello_world",
                        "level": "3.1",
                        "result": "pass",
                    },
                    {},
                ),
            ],
        )

        # "test_result" with invalid result
        action = TestMonitorAction(job)
        action.test_suite_name = "monitor-1"
        action.logger = RecordingLogger()
        action.level = "3.1"
        data = {"result": "PASS", "test_case_id": "hello world"}
        self.assertTrue(action.check_patterns("test_result", MockConnection(data)))
        self.assertEqual(
            action.logger.logs,
            [
                ("info", "ok: test case found", {}),
                ("error", "error: bad test results: %s", "PASS", {}),
            ],
        )

        # no "test_result", just "test_case_id" and "measurement"
        action = TestMonitorAction(job)
        action.test_suite_name = "monitor-1"
        action.logger = RecordingLogger()
        action.level = "3.1"
        data = {"test_case_id": "hello world", "measurement": 45.6}
        self.assertTrue(action.check_patterns("test_result", MockConnection(data)))
        self.assertEqual(
            action.logger.logs,
            [
                ("info", "ok: test case found", {}),
                ("debug", "test_case_id: %s", "hello_world", {}),
                (
                    "results",
                    {
                        "definition": "monitor-1",
                        "case": "hello_world",
                        "level": "3.1",
                        "result": "pass",
                        "measurement": 45.6,
                    },
                    {},
                ),
            ],
        )

        # no "test_result", just "test_case_id", "measurement" and units
        action = TestMonitorAction(job)
        action.test_suite_name = "monitor-1"
        action.logger = RecordingLogger()
        action.level = "3.1"
        data = {"test_case_id": "hello world", "measurement": 45.6, "units": "ms"}
        self.assertTrue(action.check_patterns("test_result", MockConnection(data)))
        self.assertEqual(
            action.logger.logs,
            [
                ("info", "ok: test case found", {}),
                ("debug", "test_case_id: %s", "hello_world", {}),
                (
                    "results",
                    {
                        "definition": "monitor-1",
                        "case": "hello_world",
                        "level": "3.1",
                        "result": "pass",
                        "measurement": 45.6,
                        "units": "ms",
                    },
                    {},
                ),
            ],
        )
