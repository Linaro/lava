# Copyright (C) 2023 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import MagicMock, call, patch

from lava_common.exceptions import ConnectionClosedError, TestError
from lava_dispatcher.actions.test.shell import TestShellAction
from lava_dispatcher.actions.test_strategy import TestShell

from ...test_basic import LavaDispatcherTestCase


class Mockmatch:
    def __init__(self, data):
        self.data = data

    def groups(self):
        return self.data


class MockConnection:
    def __init__(self, data):
        self.match = Mockmatch(data)


class TestTestShell(LavaDispatcherTestCase):
    def test_accepts(self):
        self.assertEqual(
            TestShell.accepts(None, {}), (False, '"definitions" not in parameters')
        )
        self.assertEqual(
            TestShell.accepts(None, {"definitions": {}}), (True, "accepted")
        )

    def test_check_patterns(self):
        job = self.create_simple_job()
        # "exit"
        action = TestShellAction(job)
        with self.assertLogs(action.logger) as action_logs:
            self.assertIs(action.check_patterns("exit", None), False)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [("INFO", "ok: lava_test_shell seems to have completed")],
        )

        # "eof"
        action = TestShellAction(job)
        with self.assertRaises(ConnectionClosedError):
            action.check_patterns("eof", None)

        # "timeout"
        action = TestShellAction(job)
        with self.assertRaisesRegex(AssertionError, "no logs"), self.assertLogs(
            action.logger
        ) as action_logs:
            self.assertIs(action.check_patterns("timeout", None), True)

    def test_signal_start_run(self):
        job = self.create_simple_job()

        # "signal.STARTRUN"
        action = TestShellAction(job)
        action.parameters = {"namespace": "common"}
        action.data = {}
        action.set_namespace_data(
            action="test-definition",
            label="test-definition",
            key="testdef_index",
            value=["DEFINITION"],
        )
        action.set_namespace_data(
            action="repo-action", label="repo-action", key="uuid-list", value=["UUID"]
        )

        data = ("STARTRUN", "0_DEFINITION UUID")
        with self.assertLogs(action.logger, level="DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                ("DEBUG", "Received signal: <STARTRUN> 0_DEFINITION UUID"),
                ("INFO", "Starting test lava.0_DEFINITION (UUID)"),
                ("INFO", "Skipping test definition patterns."),
            ],
        )
        self.assertEqual(
            action.current_run,
            {
                "case": "0_DEFINITION",
                "definition": "lava",
                "result": "fail",
                "uuid": "UUID",
            },
        )
        self.assertEqual(action.patterns, {})

        # "signal.STARTRUN exception"
        action = TestShellAction(job)

        data = ("STARTRUN", "0_DEFINITIO")
        with self.assertRaises(TestError):
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)

    def test_signal_end_run(self):
        counts = 0

        def monotonic():
            nonlocal counts
            counts += 1
            return counts

        job = self.create_simple_job()

        # "signal.ENDRUN"
        action = TestShellAction(job)
        action.logger.results = MagicMock()
        action.parameters = {"namespace": "common"}
        action.data = {}
        action.set_namespace_data(
            action="test-definition",
            label="test-definition",
            key="testdef_index",
            value=["DEFINITION"],
        )
        action.set_namespace_data(
            action="repo-action", label="repo-action", key="uuid-list", value=["UUID"]
        )

        data = ("ENDRUN", "0_DEFINITION UUID")
        with self.assertLogs(action.logger, "DEBUG") as action_logs, patch(
            "time.monotonic", monotonic
        ):
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                ("DEBUG", "Received signal: <ENDRUN> 0_DEFINITION UUID"),
                ("INFO", "Ending use of test pattern."),
                ("INFO", "Ending test lava.0_DEFINITION (UUID), duration 1.00"),
            ],
        )
        action.logger.results.assert_called_once_with(
            {
                "definition": "lava",
                "case": "0_DEFINITION",
                "uuid": "UUID",
                "repository": None,
                "path": None,
                "duration": "2.00",
                "result": "pass",
                "revision": "unspecified",
                "namespace": "common",
            }
        )
        self.assertIsNone(action.current_run)

        # "signal.ENDRUN exception"
        action = TestShellAction(job)

        data = ("ENDRUN", "0_DEFINITIO")
        with self.assertRaises(TestError):
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)

    def test_signal_end_run_handle_expected(self):
        job = self.create_simple_job()
        action = TestShellAction(job)
        expected_tcs = ["tc1", "tc2", "tc3", "tc4"]
        action.report = {
            "tc1": "pass",
            "tc2": "fail",
            "tc5": "pass",
            "tc6": {"set": "set1", "result": "fail"},
        }

        action.logger.results = MagicMock()
        action.signal_end_run = MagicMock()
        action.parameters = {"namespace": "common"}
        action.data = {}
        action.set_namespace_data(
            action="test",
            label="UUID",
            key="testdef_expected",
            value=expected_tcs,
        )

        # The expected test cases list handler is triggered on "signal.ENDRUN".
        data = ("ENDRUN", "0_DEFINITION UUID")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)

        # Test that missing test case are sorted and reported as 'fail'.
        action.logger.results.assert_has_calls(
            [
                call(
                    {
                        "definition": "0_DEFINITION",
                        "case": "tc3",
                        "result": "fail",
                        "level": None,
                        "extra": {
                            "reason": "missing expected test cases are reported as 'fail' by LAVA."
                        },
                    }
                ),
                call(
                    {
                        "definition": "0_DEFINITION",
                        "case": "tc4",
                        "result": "fail",
                        "level": None,
                        "extra": {
                            "reason": "missing expected test cases are reported as 'fail' by LAVA."
                        },
                    }
                ),
            ],
            any_order=False,
        )

        # Test that warning logs appear for both missing and unexpected test cases.
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                ("DEBUG", "Received signal: <ENDRUN> 0_DEFINITION UUID"),
                ("WARNING", "Reporting missing expected test cases as 'fail' ..."),
                ("WARNING", "Unexpected test result: tc5: pass"),
                (
                    "WARNING",
                    "Unexpected test result: tc6: {'set': 'set1', 'result': 'fail'}",
                ),
            ],
        )

    def test_signal_start_end_tc(self):
        job = self.create_simple_job()

        # "signal.STARTTC"
        action = TestShellAction(job)
        action.logger.marker = MagicMock()

        data = ("STARTTC", "TESTCASE")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [("DEBUG", "Received signal: <STARTTC> TESTCASE")],
        )
        action.logger.marker.assert_called_once_with(
            {"case": "TESTCASE", "type": "start_test_case"}
        )

        # "signal.ENDTC"
        action = TestShellAction(job)
        action.logger.marker = MagicMock()

        data = ("ENDTC", "TESTCASE")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [("DEBUG", "Received signal: <ENDTC> TESTCASE")],
        )
        action.logger.marker.assert_called_once_with(
            {"case": "TESTCASE", "type": "end_test_case"}
        )

    def test_signal_testcase(self):
        job = self.create_simple_job()

        # "signal.TESTCASE without test_uuid"
        action = TestShellAction(job)
        action.logger.marker = MagicMock()

        data = ("TESTCASE", "hello")
        with self.assertRaises(TestError), self.assertLogs(
            action.logger, "DEBUG"
        ) as action_logs:
            action.check_patterns("signal", MockConnection(data))
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                ("DEBUG", "Received signal: <TESTCASE> hello"),
                (
                    "ERROR",
                    "Unknown test uuid. The STARTRUN signal for this test action was not received correctly.",
                ),
            ],
        )
        action.logger.marker.assert_called_once_with(
            {"case": "hello", "type": "test_case"}
        )

        # "signal.TESTCASE malformed parameters"
        action = TestShellAction(job)
        action.logger.marker = MagicMock()
        action.signal_director.test_uuid = "UUID"

        data = ("TESTCASE", "hello")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                ("DEBUG", "Received signal: <TESTCASE> hello"),
                ("ERROR", 'Ignoring malformed parameter for signal: "hello". '),
            ],
        )
        action.logger.marker.assert_called_once_with(
            {"case": "hello", "type": "test_case"}
        )

        # "signal.TESTCASE missing TEST_CASE_ID"
        action = TestShellAction(job)
        action.logger.marker = MagicMock()
        action.signal_director.test_uuid = "UUID"

        data = ("TESTCASE", "TEST_CASE=e")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                ("DEBUG", "Received signal: <TESTCASE> TEST_CASE=e"),
                (
                    "ERROR",
                    "Test case results without test_case_id (probably a sign of an incorrect parsing pattern being used): {'test_case': 'e'}",
                ),
            ],
        )
        action.logger.marker.assert_called_once_with(
            {"case": "TEST_CASE=e", "type": "test_case"}
        )

        # "signal.TESTCASE missing RESULT"
        action = TestShellAction(job)
        action.logger.marker = MagicMock()
        action.signal_director.test_uuid = "UUID"

        data = ("TESTCASE", "TEST_CASE_ID=case-id")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                ("DEBUG", "Received signal: <TESTCASE> TEST_CASE_ID=case-id"),
                (
                    "ERROR",
                    "Test case results without result (probably a sign of an incorrect parsing pattern being used): {'test_case_id': 'case-id', 'result': 'unknown'}",
                ),
            ],
        )
        action.logger.marker.assert_called_once_with(
            {"case": "case-id", "type": "test_case"}
        )

        # "signal.TESTCASE"
        action = TestShellAction(job)
        action.logger.marker = MagicMock()
        action.logger.results = MagicMock()
        action.signal_director.test_uuid = "UUID"

        data = ("TESTCASE", "RESULT=pass TEST_CASE_ID=case_id")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                (
                    "DEBUG",
                    "Received signal: <TESTCASE> RESULT=pass TEST_CASE_ID=case_id",
                ),
            ],
        )
        action.logger.marker.assert_called_once_with(
            {"case": "RESULT=pass", "type": "test_case"}
        )
        action.logger.results.assert_called_once_with(
            {"definition": None, "case": "case_id", "result": "pass"}
        )

        # "signal.TESTCASE with measurement"
        action = TestShellAction(job)
        action.logger.marker = MagicMock()
        action.logger.results = MagicMock()
        action.signal_director.test_uuid = "UUID"

        data = ("TESTCASE", "RESULT=pass TEST_CASE_ID=case_id MEASUREMENT=1234")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                (
                    "DEBUG",
                    "Received signal: <TESTCASE> RESULT=pass TEST_CASE_ID=case_id MEASUREMENT=1234",
                )
            ],
        )
        action.logger.marker.assert_called_once_with(
            {"case": "RESULT=pass", "type": "test_case"}
        )
        action.logger.results.assert_called_once_with(
            {
                "definition": None,
                "case": "case_id",
                "result": "pass",
                "measurement": 1234.0,
            }
        )

        # "signal.TESTCASE with measurement and unit"
        action = TestShellAction(job)
        action.logger.marker = MagicMock()
        action.logger.results = MagicMock()
        action.signal_director.test_uuid = "UUID"

        data = ("TESTCASE", "RESULT=pass TEST_CASE_ID=case_id MEASUREMENT=1234 UNITS=s")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                (
                    "DEBUG",
                    "Received signal: <TESTCASE> RESULT=pass TEST_CASE_ID=case_id MEASUREMENT=1234 UNITS=s",
                )
            ],
        )
        action.logger.marker.assert_called_once_with(
            {"case": "RESULT=pass", "type": "test_case"}
        )
        action.logger.results.assert_called_once_with(
            {
                "definition": None,
                "case": "case_id",
                "result": "pass",
                "measurement": 1234.0,
                "units": "s",
            }
        )

    def test_signal_test_feedback(self):
        job = self.create_simple_job()

        # "signal.TESTFEEDBACK missing ns"
        action = TestShellAction(job)

        data = ("TESTFEEDBACK", "FEED1")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                ("DEBUG", "Received signal: <TESTFEEDBACK> FEED1"),
                ("ERROR", "%s is not a valid namespace"),
            ],
        )

    def test_signal_test_reference(self):
        job = self.create_simple_job()

        # "signal.TESTREFERENCE missing parameters"
        action = TestShellAction(job)

        data = ("TESTREFERENCE", "")
        with self.assertRaises(TestError), self.assertLogs(
            action.logger, "DEBUG"
        ) as action_logs:
            action.check_patterns("signal", MockConnection(data))

        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                ("DEBUG", "Received signal: <TESTREFERENCE> "),
            ],
        )

        # "signal.TESTREFERENCE"
        action = TestShellAction(job)
        action.logger.results = MagicMock()

        data = ("TESTREFERENCE", "case-id pass http://example.com")
        with self.assertLogs(action.logger, "DEBUG") as action_logs:
            self.assertIs(action.check_patterns("signal", MockConnection(data)), True)
        self.assertEqual(
            [(r.levelname, r.message) for r in action_logs.records],
            [
                (
                    "DEBUG",
                    "Received signal: <TESTREFERENCE> case-id pass http://example.com",
                )
            ],
        )
        action.logger.results.assert_called_once_with(
            {
                "case": "case-id",
                "definition": None,
                "result": "pass",
                "reference": "http://example.com",
            }
        )
