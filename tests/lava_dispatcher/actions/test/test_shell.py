# Copyright (C) 2023 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import time

import pytest

from lava_common.exceptions import ConnectionClosedError, TestError
from lava_dispatcher.actions.test.shell import TestShell, TestShellAction
from lava_dispatcher.job import Job
from tests.utils import RecordingLogger


class Mockmatch:
    def __init__(self, data):
        self.data = data

    def groups(self):
        return self.data


class MockConnection:
    def __init__(self, data):
        self.match = Mockmatch(data)


def test_accepts():
    assert TestShell.accepts(None, {}) == (False, '"definitions" not in parameters')
    assert TestShell.accepts(None, {"definitions": {}}) == (True, "accepted")


def test_check_patterns():
    # "exit"
    action = TestShellAction()
    action.logger = RecordingLogger()
    assert action.check_patterns("exit", None) is False
    assert action.logger.logs == [
        ("info", "ok: lava_test_shell seems to have completed", {})
    ]

    # "eof"
    action = TestShellAction()
    action.logger = RecordingLogger()
    with pytest.raises(ConnectionClosedError):
        action.check_patterns("eof", None)

    # "timeout"
    action = TestShellAction()
    action.logger = RecordingLogger()
    assert action.check_patterns("timeout", None) is True
    assert action.logger.logs == []


def test_signal_start_run():
    job = Job(1234, {}, None)

    # "signal.STARTRUN"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()
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
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        ("debug", "Received signal: <STARTRUN> 0_DEFINITION UUID", {}),
        ("info", "Starting test lava.%s (%s)", "0_DEFINITION", "UUID", {}),
        ("info", "Skipping test definition patterns.", {}),
    ]
    assert action.current_run == {
        "case": "0_DEFINITION",
        "definition": "lava",
        "result": "fail",
        "uuid": "UUID",
    }
    assert action.patterns == {}

    # "signal.STARTRUN exception"
    action = TestShellAction()
    action.logger = RecordingLogger()

    data = ("STARTRUN", "0_DEFINITIO")
    with pytest.raises(TestError):
        action.check_patterns("signal", MockConnection(data)) is True


def test_signal_end_run(monkeypatch):
    counts = 0

    def monotonic():
        nonlocal counts
        counts += 1
        return counts

    monkeypatch.setattr(time, "monotonic", monotonic)

    job = Job(1234, {}, None)

    # "signal.ENDRUN"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()
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
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        ("debug", "Received signal: <ENDRUN> 0_DEFINITION UUID", {}),
        ("info", "Ending use of test pattern.", {}),
        (
            "info",
            "Ending test lava.%s (%s), duration %.02f",
            "0_DEFINITION",
            "UUID",
            1,
            {},
        ),
        (
            "results",
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
            },
            {},
        ),
    ]
    assert action.current_run is None

    # "signal.ENDRUN exception"
    action = TestShellAction()
    action.logger = RecordingLogger()

    data = ("ENDRUN", "0_DEFINITIO")
    with pytest.raises(TestError):
        action.check_patterns("signal", MockConnection(data)) is True


def test_signal_start_end_tc():
    job = Job(1234, {}, None)

    # "signal.STARTTC"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()

    data = ("STARTTC", "TESTCASE")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        ("debug", "Received signal: <STARTTC> TESTCASE", {}),
        ("marker", {"case": "TESTCASE", "type": "start_test_case"}, {}),
    ]

    # "signal.ENDTC"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()

    data = ("ENDTC", "TESTCASE")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        ("debug", "Received signal: <ENDTC> TESTCASE", {}),
        ("marker", {"case": "TESTCASE", "type": "end_test_case"}, {}),
    ]


def test_signal_testcase():
    job = Job(1234, {}, None)

    # "signal.TESTCASE without test_uuid"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()

    data = ("TESTCASE", "hello")
    with pytest.raises(TestError):
        action.check_patterns("signal", MockConnection(data))
    assert action.logger.logs == [
        ("debug", "Received signal: <TESTCASE> hello", {}),
        ("marker", {"case": "hello", "type": "test_case"}, {}),
        (
            "error",
            "Unknown test uuid. The STARTRUN signal for this test action was not received correctly.",
            {},
        ),
    ]

    # "signal.TESTCASE malformed parameters"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()
    action.signal_director.test_uuid = "UUID"

    data = ("TESTCASE", "hello")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        ("debug", "Received signal: <TESTCASE> hello", {}),
        ("marker", {"case": "hello", "type": "test_case"}, {}),
        ("error", 'Ignoring malformed parameter for signal: "hello". ', {}),
    ]

    # "signal.TESTCASE missing TEST_CASE_ID"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()
    action.signal_director.test_uuid = "UUID"

    data = ("TESTCASE", "TEST_CASE=e")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        ("debug", "Received signal: <TESTCASE> TEST_CASE=e", {}),
        ("marker", {"case": "TEST_CASE=e", "type": "test_case"}, {}),
        (
            "error",
            "Test case results without test_case_id (probably a sign of an incorrect parsing pattern being used): {'test_case': 'e'}",
            {},
        ),
    ]

    # "signal.TESTCASE missing RESULT"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()
    action.signal_director.test_uuid = "UUID"

    data = ("TESTCASE", "TEST_CASE_ID=case-id")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        ("debug", "Received signal: <TESTCASE> TEST_CASE_ID=case-id", {}),
        ("marker", {"case": "case-id", "type": "test_case"}, {}),
        (
            "error",
            "Test case results without result (probably a sign of an incorrect parsing pattern being used): {'test_case_id': 'case-id', 'result': 'unknown'}",
            {},
        ),
    ]

    # "signal.TESTCASE"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()
    action.signal_director.test_uuid = "UUID"

    data = ("TESTCASE", "RESULT=pass TEST_CASE_ID=case_id")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        ("debug", "Received signal: <TESTCASE> RESULT=pass TEST_CASE_ID=case_id", {}),
        ("marker", {"case": "RESULT=pass", "type": "test_case"}, {}),
        ("results", {"definition": None, "case": "case_id", "result": "pass"}, {}),
    ]

    # "signal.TESTCASE with measurement"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()
    action.signal_director.test_uuid = "UUID"

    data = ("TESTCASE", "RESULT=pass TEST_CASE_ID=case_id MEASUREMENT=1234")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        (
            "debug",
            "Received signal: <TESTCASE> RESULT=pass TEST_CASE_ID=case_id MEASUREMENT=1234",
            {},
        ),
        ("marker", {"case": "RESULT=pass", "type": "test_case"}, {}),
        (
            "results",
            {
                "definition": None,
                "case": "case_id",
                "result": "pass",
                "measurement": 1234.0,
            },
            {},
        ),
    ]

    # "signal.TESTCASE with measurement and unit"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()
    action.signal_director.test_uuid = "UUID"

    data = ("TESTCASE", "RESULT=pass TEST_CASE_ID=case_id MEASUREMENT=1234 UNITS=s")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        (
            "debug",
            "Received signal: <TESTCASE> RESULT=pass TEST_CASE_ID=case_id MEASUREMENT=1234 UNITS=s",
            {},
        ),
        ("marker", {"case": "RESULT=pass", "type": "test_case"}, {}),
        (
            "results",
            {
                "definition": None,
                "case": "case_id",
                "result": "pass",
                "measurement": 1234.0,
                "units": "s",
            },
            {},
        ),
    ]


def test_signal_test_feedback():
    job = Job(1234, {}, None)

    # "signal.TESTFEEDBACK missing ns"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()

    data = ("TESTFEEDBACK", "FEED1")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        ("debug", "Received signal: <TESTFEEDBACK> FEED1", {}),
        ("error", "%s is not a valid namespace", {}),
    ]


def test_signal_test_reference():
    job = Job(1234, {}, None)

    # "signal.TESTREFERENCE missing parameters"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()

    data = ("TESTREFERENCE", "")
    with pytest.raises(TestError):
        action.check_patterns("signal", MockConnection(data))
    assert action.logger.logs == [("debug", "Received signal: <TESTREFERENCE> ", {})]

    # "signal.TESTREFERENCE"
    action = TestShellAction()
    action.job = job
    action.logger = RecordingLogger()

    data = ("TESTREFERENCE", "case-id pass http://example.com")
    assert action.check_patterns("signal", MockConnection(data)) is True
    assert action.logger.logs == [
        (
            "debug",
            "Received signal: <TESTREFERENCE> case-id pass http://example.com",
            {},
        ),
        (
            "results",
            {
                "case": "case-id",
                "definition": None,
                "result": "pass",
                "reference": "http://example.com",
            },
            {},
        ),
    ]
