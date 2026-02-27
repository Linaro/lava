# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from unittest.mock import patch

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
                            "pattern": (
                                "(?P<test_case_id>.*) (?P<measurement>.*) "
                                "tcs = [0-9]* nsec"
                            ),
                            "fixupdict": {"PASS": "pass", "FAIL": "fail"},
                        }
                    ]
                },
            ),
            (False, "missing required parameters ['end', 'name']"),
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
            self.assertFalse(action.check_patterns("eof", None, {}))
        self.assertEqual(
            action.logger.logs,
            [("warning", "err: lava test monitoring reached end of file", {})],
        )
        self.assertEqual(action.errors, ["lava test monitoring reached end of file"])

        # "timeout"
        action = TestMonitorAction(job)
        action.logger = RecordingLogger()
        self.assertFalse(action.check_patterns("timeout", None, {}))
        self.assertEqual(
            action.logger.logs,
            [("warning", "err: lava test monitoring has timed out", {})],
        )
        self.assertEqual(action.errors, ["lava test monitoring has timed out"])

        # "end"
        action = TestMonitorAction(job)
        action.logger = RecordingLogger()
        self.assertFalse(action.check_patterns("end", None, {}))
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
        self.assertTrue(action.check_patterns("test_result", MockConnection(data), {}))
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
        self.assertTrue(action.check_patterns("test_result", MockConnection(data), {}))
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
        self.assertTrue(action.check_patterns("test_result", MockConnection(data), {}))
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
        self.assertTrue(action.check_patterns("test_result", MockConnection(data), {}))
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
        self.assertTrue(action.check_patterns("test_result", MockConnection(data), {}))
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
        self.assertTrue(action.check_patterns("test_result", MockConnection(data), {}))
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


class TestMonitorExpected(LavaDispatcherTestCase):
    def setUp(self):
        self.job = self.create_simple_job()
        self.action = TestMonitorAction(self.job)
        self.action.logger = RecordingLogger()
        self.action.level = "3.1"
        self.test_suite_name = "ts1"

    def test_handle_expected_all_match(self):
        self.action.report = {"tc1": "pass", "tc2": "fail"}

        self.action.handle_expected(["tc1", "tc2"], self.test_suite_name)

        self.assertEqual(self.action.logger.logs, [])

    def test_handle_expected_missing(self):
        self.action.report = {"tc1": "pass"}

        self.action.handle_expected(["tc1", "tc2", "tc3"], self.test_suite_name)

        self.assertEqual(
            self.action.logger.logs,
            [
                ("warning", "Reporting missing expected test cases as 'fail' ...", {}),
                (
                    "results",
                    {
                        "definition": self.test_suite_name,
                        "case": "tc2",
                        "result": "fail",
                        "level": "3.1",
                        "extra": {
                            "reason": "missing expected test cases are reported as 'fail' by LAVA."
                        },
                    },
                    {},
                ),
                (
                    "results",
                    {
                        "definition": self.test_suite_name,
                        "case": "tc3",
                        "result": "fail",
                        "level": "3.1",
                        "extra": {
                            "reason": "missing expected test cases are reported as 'fail' by LAVA."
                        },
                    },
                    {},
                ),
            ],
        )
        self.assertEqual(self.action.report["tc2"], "fail")
        self.assertEqual(self.action.report["tc3"], "fail")


class TestMonitorUnexpected(LavaDispatcherTestCase):
    def setUp(self):
        self.job = self.create_simple_job()
        self.action = TestMonitorAction(self.job)
        self.action.logger = RecordingLogger()

    def test_expected_case(self):
        result = self.action.handle_unexpected(["tc1", "tc2"], "tc1", "pass")
        self.assertEqual(result, "pass")
        self.assertEqual(self.action.logger.logs, [])

    def test_unexpected_fail(self):
        result = self.action.handle_unexpected(["tc1"], "tc2", "fail")
        self.assertEqual(result, "fail")
        self.assertEqual(
            self.action.logger.logs,
            [("warning", "'tc2' not found in expected test case list!", {})],
        )

    def test_unexpected_pass(self):
        result = self.action.handle_unexpected(["tc1"], "tc2", "pass")
        self.assertEqual(result, "fail")
        self.assertEqual(
            self.action.logger.logs,
            [
                ("warning", "'tc2' not found in expected test case list!", {}),
                (
                    "warning",
                    "Forcing unexpected 'tc2' result 'pass' to 'fail' ...",
                    {},
                ),
            ],
        )


class TestMonitorSummary(LavaDispatcherTestCase):
    def setUp(self):
        self.job = self.create_simple_job()
        self.action = TestMonitorAction(self.job)
        self.action.logger = RecordingLogger()
        self.action.level = "3.1"
        self.test_suite_name = "ts1"

    def test_handle_summary(self):
        self.action.report = {"tc1": "pass", "tc2": "fail"}

        self.action.handle_summary(self.test_suite_name)

        self.assertEqual(len(self.action.logger.logs), 3)
        self.assertEqual(self.action.logger.logs[0][0], "debug")
        self.assertEqual(self.action.logger.logs[0][1], "--- ts1 Test Report ---")
        self.assertEqual(self.action.logger.logs[1][0], "debug")
        self.assertIn("tc1: pass", self.action.logger.logs[1][1])
        self.assertIn("tc2: fail", self.action.logger.logs[1][1])
        self.assertEqual(self.action.logger.logs[2][0], "debug")
        self.assertIn("End", self.action.logger.logs[2][1])

    def test_handle_summary_empty(self):
        self.action.report = {}

        self.action.handle_summary(self.test_suite_name)

        self.assertEqual(self.action.logger.logs, [])


class TestMonitorCleanup(LavaDispatcherTestCase):
    def setUp(self):
        self.job = self.create_simple_job()
        self.action = TestMonitorAction(self.job)

    def test_cleanup_no_run(self):
        monitors = [
            {
                "name": "monitor1",
                "expected": ["tc1", "tc2"],
            },
            {
                "name": "monitor2",
                "expected": ["tc3", "tc4"],
            },
        ]
        self.action.parameters = {"monitors": monitors}
        # No report for monitor2
        self.action.reports = {
            "monitor1": {"results": {"tc1": "pass", "tc2": "pass"}, "ran": True},
        }

        with patch.object(self.action, "handle_expected") as mock_handle_expected:
            self.action.cleanup(None, None)
            self.assertEqual(self.action.report, {})
            mock_handle_expected.assert_called_once_with(["tc3", "tc4"], "monitor2")

    def test_cleanup_all_ran(self):
        job = self.create_simple_job()
        action = TestMonitorAction(job)
        monitors = [
            {
                "name": "monitor1",
                "expected": ["tc1", "tc2"],
            },
            {
                "name": "monitor2",
                "expected": ["tc3", "tc4"],
            },
        ]
        action.parameters = {"monitors": monitors}
        action.reports = {
            "monitor1": {"results": {"tc1": "pass", "tc2": "pass"}, "ran": True},
            "monitor2": {"results": {"tc3": "pass", "tc4": "pass"}, "ran": True},
        }

        with patch.object(action, "handle_expected") as mock_handle_expected:
            action.cleanup(None, None)
            mock_handle_expected.assert_not_called()

    def test_cleanup_incomplete_run(self):
        monitors = [
            {
                "name": "monitor1",
                "expected": ["tc1", "tc2"],
            },
            {
                "name": "monitor2",
                "expected": ["tc3", "tc4"],
            },
        ]
        self.action.parameters = {"monitors": monitors}
        self.action.reports = {
            "monitor1": {"results": {"tc1": "pass", "tc2": "pass"}, "ran": True},
            # monitor2 fails to finish and only one of two results saved.
            "monitor2": {"results": {"tc3": "pass"}, "ran": False},
        }

        with patch.object(self.action, "handle_expected") as mock_handle_expected:
            self.action.cleanup(None, None)
            self.assertEqual(self.action.report, {"tc3": "pass"})
            mock_handle_expected.assert_called_once_with(["tc3", "tc4"], "monitor2")

    def test_cleanup_no_expected(self):
        job = self.create_simple_job()
        action = TestMonitorAction(job)
        monitors = [
            {
                "name": "monitor1",
            },
            {
                "name": "monitor2",
                "expected": ["tc3", "tc4"],
            },
        ]
        action.parameters = {"monitors": monitors}
        action.reports = {
            "monitor1": {"results": {}, "ran": False},
            "monitor2": {"results": {"tc3": "pass"}, "ran": False},
        }

        with patch.object(action, "handle_expected") as mock_handle_expected:
            action.cleanup(None, None)
            mock_handle_expected.assert_called_once_with(["tc3", "tc4"], "monitor2")
