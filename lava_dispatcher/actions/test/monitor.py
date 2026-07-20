# Copyright (C) 2014 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

import pexpect

from lava_common.decorators import nottest
from lava_common.exceptions import ConnectionClosedError, LAVATimeoutError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.test.mixins import ReportMixin
from lava_dispatcher.logical import RetryAction

if TYPE_CHECKING:
    from typing import Any

    from lava_dispatcher.job import Job
    from lava_dispatcher.shell import ShellSession


@nottest
class TestMonitorRetry(RetryAction):
    name = "lava-test-monitor-retry"
    description = "Retry wrapper for lava-test-monitor"
    summary = "Retry support for Lava Test Monitoring"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(TestMonitorAction(self.job))


@nottest
class TestMonitorAction(ReportMixin, Action):
    """
    Watch the DUT output and match known results strings without any interaction.
    """

    name = "lava-test-monitor"
    description = "Executing lava-test-monitor"
    summary = "Lava Test Monitor"
    timeout_exception = LAVATimeoutError

    def __init__(self, job: Job):
        super().__init__(job)
        self.test_suite_name = None
        self.reports: dict[str, dict[str, Any]] = {}
        self.report = {}
        self.fixupdict = {}
        self.patterns = {}

    @staticmethod
    def _normalize_monitor_name(monitor_name: str) -> str:
        return monitor_name.replace(" ", "-").lower()

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        if not connection:
            raise ConnectionClosedError("Connection closed")
        for monitor in self.parameters["monitors"]:
            self.report = {}
            self.test_suite_name = self._normalize_monitor_name(monitor["name"])
            self.reports[self.test_suite_name] = {"results": self.report, "ran": False}

            self.fixupdict = monitor.get("fixupdict")

            # pattern order is important because we want to match the end before
            # it can possibly get confused with a test result
            self.patterns = {}
            self.patterns["eof"] = pexpect.EOF
            self.patterns["timeout"] = pexpect.TIMEOUT
            self.patterns["end"] = monitor["end"]
            self.patterns["test_result"] = monitor["pattern"]

            # Find the start string before parsing any output.
            self.logger.info("Waiting for start message: %s", monitor["start"])
            connection.prompt_str = monitor["start"]
            connection.wait()
            self.logger.info("ok: start string found, lava test monitoring started")

            if max_end_time is None:
                keep_running_timeout = connection.timeout.duration
            else:
                keep_running_timeout = max_end_time - time.monotonic()
            while self._keep_running(connection, monitor, timeout=keep_running_timeout):
                pass

            if expected := monitor.get("expected"):
                self.handle_expected(expected, self.test_suite_name)

            self.reports[self.test_suite_name]["ran"] = True
            self.handle_summary(self.test_suite_name)
        return connection

    def _keep_running(self, connection: ShellSession, monitor, timeout: float = 120.0):
        self.logger.debug("test monitoring timeout: %d seconds", timeout)
        with connection._expect_exc_wrapper():
            retval = connection.raw_connection.expect(
                list(self.patterns.values()), timeout=timeout
            )
        return self.check_patterns(
            list(self.patterns.keys())[retval], connection, monitor
        )

    def check_patterns(self, event, connection: ShellSession, monitor):
        """
        Defines the base set of pattern responses.
        Stores the results of testcases inside the TestAction
        Call from subclasses before checking subclass-specific events.
        """
        ret_val = False
        if event == "eof":
            self.logger.warning("err: lava test monitoring reached end of file")
            self.errors_add("lava test monitoring reached end of file")
            raise ConnectionClosedError("Connection closed")
        elif event == "timeout":
            self.logger.warning("err: lava test monitoring has timed out")
            self.errors_add("lava test monitoring has timed out")
        elif event == "end":
            self.logger.info("ok: end string found, lava test monitoring stopped")
        elif event == "test_result":
            self.logger.info("ok: test case found")
            match = connection.raw_connection.match.groupdict()
            if "result" in match:
                if self.fixupdict:
                    if match["result"] in self.fixupdict:
                        match["result"] = self.fixupdict[match["result"]]
                if match["result"] not in ("pass", "fail", "skip", "unknown"):
                    self.logger.error("error: bad test results: %s", match["result"])
                else:
                    if "test_case_id" in match:
                        case_id = match["test_case_id"].strip().lower()
                        # remove special characters to form a valid test case id
                        case_id = re.sub(r"\W+", "_", case_id)
                        self.logger.debug("test_case_id: %s", case_id)
                        results = {
                            "definition": self.test_suite_name,
                            "case": case_id,
                            "level": self.level,
                            "result": match["result"],
                        }
                        if "measurement" in match:
                            results.update({"measurement": match["measurement"]})
                        if "units" in match:
                            results.update({"units": match["units"]})
                        if expected := monitor.get("expected"):
                            results["result"] = self.handle_unexpected(
                                expected, results["case"], results["result"]
                            )
                        self.logger.results(results)
                        self.report[case_id] = results["result"]
            else:
                if all(x in match for x in ["test_case_id", "measurement"]):
                    if match["measurement"] and match["test_case_id"]:
                        case_id = match["test_case_id"].strip().lower()
                        # remove special characters to form a valid test case id
                        case_id = re.sub(r"\W+", "_", case_id)
                        self.logger.debug("test_case_id: %s", case_id)
                        results = {
                            "definition": self.test_suite_name,
                            "case": case_id,
                            "level": self.level,
                            "result": "pass",
                            "measurement": float(match["measurement"]),
                        }
                        if "units" in match:
                            results.update({"units": match["units"]})
                        if expected := monitor.get("expected"):
                            results["result"] = self.handle_unexpected(
                                expected, results["case"], results["result"]
                            )
                        self.logger.results(results)
                        self.report[case_id] = results["result"]
            ret_val = True
        return ret_val

    def cleanup(self, connection, max_end_time=None):
        super().cleanup(connection, max_end_time=None)

        monitors = self.parameters.get("monitors", [])
        for monitor in monitors:
            expected = monitor.get("expected")
            if not expected:
                continue

            test_suite_name = self._normalize_monitor_name(monitor["name"])

            if self.reports.get(test_suite_name, {}).get("ran"):
                continue

            self.report = self.reports.get(test_suite_name, {}).get("results", {})
            self.handle_expected(expected, test_suite_name)
