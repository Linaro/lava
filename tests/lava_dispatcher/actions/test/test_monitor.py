# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import logging

from lava_dispatcher.actions.test.monitor import TestMonitor, TestMonitorAction

from tests.lava_dispatcher.utils import RecordingLogger


def test_accepts():
    assert TestMonitor.accepts(None, {}) == (False, '"monitors" not in parameters')
    assert TestMonitor.accepts(None, {"monitors": {}}) == (True, "accepted")

    # Missing some parameters
    assert TestMonitor.accepts(
        None,
        {
            "monitors": [
                {
                    "start": "BOOTING ZEPHYR",
                    "end": "PROJECT EXECUTION SUCCESSFUL",
                    "pattern": "(?P<test_case_id>.*) (?P<measurement>.*) tcs = [0-9]* nsec",
                    "fixupdict": {"PASS": "pass", "FAIL": "fail"},
                }
            ]
        },
    ) == (False, "missing required parameter 'name'")

    # Working example
    assert TestMonitor.accepts(
        None,
        {
            "monitors": [
                {
                    "name": "tests",
                    "start": "BOOTING ZEPHYR",
                    "end": "PROJECT EXECUTION SUCCESSFUL",
                    "pattern": "(?P<test_case_id>.*) (?P<measurement>.*) tcs = [0-9]* nsec",
                    "fixupdict": {"PASS": "pass", "FAIL": "fail"},
                },
                {
                    "name": "tests",
                    "start": "Running test suite common_test",
                    "end": "PROJECT EXECUTION SUCCESSFUL",
                    "pattern": "(?P<result>(PASS|FAIL)) - (?P<test_case_id>.*)\\.",
                    "fixupdict": {"PASS: pass", "FAIL,: ,fail"},
                },
            ]
        },
    ) == (True, "accepted")


class Mockmatch:
    def __init__(self, data):
        self.data = data

    def groupdict(self):
        return self.data


class MockConnection:
    def __init__(self, data):
        self.match = Mockmatch(data)


def test_check_patterns():
    # "eof"
    action = TestMonitorAction()
    action.logger = RecordingLogger()
    assert action.check_patterns("eof", None) is False
    assert action.logger.logs == [
        ("warning", "err: lava test monitoring reached end of file", {})
    ]
    assert action.errors == ["lava test monitoring reached end of file"]
    assert action.results == {"status": "failed"}

    # "timeout"
    action = TestMonitorAction()
    action.logger = RecordingLogger()
    assert action.check_patterns("timeout", None) is False
    assert action.logger.logs == [
        ("warning", "err: lava test monitoring has timed out", {})
    ]
    assert action.errors == ["lava test monitoring has timed out"]
    assert action.results == {"status": "failed"}

    # "end"
    action = TestMonitorAction()
    action.logger = RecordingLogger()
    assert action.check_patterns("end", None) is False
    assert action.logger.logs == [
        ("info", "ok: end string found, lava test monitoring stopped", {})
    ]
    assert action.errors == []
    assert action.results == {"status": "passed"}

    # "test_result"
    action = TestMonitorAction()
    action.test_suite_name = "monitor-1"
    action.logger = RecordingLogger()
    action.level = "3.1"
    data = {"result": "pass", "test_case_id": "hello world"}
    assert action.check_patterns("test_result", MockConnection(data)) is True
    assert action.logger.logs == [
        ("info", "ok: test case found", {}),
        ("debug", "test_case_id: %s", "hello_world", {}),
        (
            "results",
            {
                "definition": "monitor-1",
                "case": "hello_world",
                "level": "3.1",
                "result": "pass",
                "extra": {"test_case_id": "hello world"},
            },
            {},
        ),
    ]
    assert action.results == {}

    # "test_result" with "measurement" and "units"
    action = TestMonitorAction()
    action.test_suite_name = "monitor-1"
    action.logger = RecordingLogger()
    action.level = "3.1"
    data = {
        "result": "pass",
        "test_case_id": "hello world",
        "measurement": 1.3,
        "units": "s",
    }
    assert action.check_patterns("test_result", MockConnection(data)) is True
    assert action.logger.logs == [
        ("info", "ok: test case found", {}),
        ("debug", "test_case_id: %s", "hello_world", {}),
        (
            "results",
            {
                "definition": "monitor-1",
                "case": "hello_world",
                "level": "3.1",
                "result": "pass",
                "extra": {"test_case_id": "hello world"},
                "measurement": 1.3,
                "units": "s",
            },
            {},
        ),
    ]
    assert action.results == {}

    # "test_result" with fixupdict
    action = TestMonitorAction()
    action.test_suite_name = "monitor-1"
    action.logger = RecordingLogger()
    action.level = "3.1"
    action.fixupdict = {"PASS": "pass"}
    data = {"result": "PASS", "test_case_id": "hello world"}
    assert action.check_patterns("test_result", MockConnection(data)) is True
    assert action.logger.logs == [
        ("info", "ok: test case found", {}),
        ("debug", "test_case_id: %s", "hello_world", {}),
        (
            "results",
            {
                "definition": "monitor-1",
                "case": "hello_world",
                "level": "3.1",
                "result": "pass",
                "extra": {"test_case_id": "hello world"},
            },
            {},
        ),
    ]

    # "test_result" with invalid result
    action = TestMonitorAction()
    action.test_suite_name = "monitor-1"
    action.logger = RecordingLogger()
    action.level = "3.1"
    data = {"result": "PASS", "test_case_id": "hello world"}
    assert action.check_patterns("test_result", MockConnection(data)) is True
    assert action.logger.logs == [
        ("info", "ok: test case found", {}),
        ("error", "error: bad test results: %s", "PASS", {}),
    ]

    # no "test_result", just "test_case_id" and "measurement"
    action = TestMonitorAction()
    action.test_suite_name = "monitor-1"
    action.logger = RecordingLogger()
    action.level = "3.1"
    data = {"test_case_id": "hello world", "measurement": 45.6}
    assert action.check_patterns("test_result", MockConnection(data)) is True
    assert action.logger.logs == [
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
                "extra": {"test_case_id": "hello world"},
            },
            {},
        ),
    ]

    # no "test_result", just "test_case_id", "measurement" and units
    action = TestMonitorAction()
    action.test_suite_name = "monitor-1"
    action.logger = RecordingLogger()
    action.level = "3.1"
    data = {"test_case_id": "hello world", "measurement": 45.6, "units": "ms"}
    assert action.check_patterns("test_result", MockConnection(data)) is True
    assert action.logger.logs == [
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
                "extra": {"test_case_id": "hello world"},
            },
            {},
        ),
    ]
