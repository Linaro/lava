# Copyright (C) 2014 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import re
from collections import OrderedDict
from typing import TYPE_CHECKING

import pexpect

from lava_common.decorators import nottest
from lava_common.exceptions import ConnectionClosedError, LAVATimeoutError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.test.mixins import ReportMixin
from lava_dispatcher.logical import RetryAction

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


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
        self.report = {}
        self.fixupdict = {}
        self.patterns = {}

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        if not connection:
            raise ConnectionClosedError("Connection closed")
        for monitor in self.parameters["monitors"]:
            self.report = {}
            self.test_suite_name = monitor["name"].replace(" ", "-").lower()

            self.fixupdict = monitor.get("fixupdict")

            # pattern order is important because we want to match the end before
            # it can possibly get confused with a test result
            self.patterns = OrderedDict()
            self.patterns["eof"] = pexpect.EOF
            self.patterns["timeout"] = pexpect.TIMEOUT
            self.patterns["end"] = monitor["end"]
            self.patterns["test_result"] = monitor["pattern"]

            # Find the start string before parsing any output.
            self.logger.info("Waiting for start message: %s", monitor["start"])
            connection.prompt_str = monitor["start"]
            connection.wait()
            self.logger.info("ok: start string found, lava test monitoring started")

            with connection.test_connection() as test_connection:
                while self._keep_running(
                    test_connection, timeout=test_connection.timeout
                ):
                    pass

            if expected := monitor.get("expected"):
                self.handle_expected(expected, self.test_suite_name)

            self.handle_summary(self.test_suite_name)
        return connection

    def _keep_running(self, test_connection, timeout=120):
        self.logger.debug("test monitoring timeout: %d seconds", timeout)
        retval = test_connection.expect(list(self.patterns.values()), timeout=timeout)
        return self.check_patterns(list(self.patterns.keys())[retval], test_connection)

    def check_patterns(self, event, test_connection):
        """
        Defines the base set of pattern responses.
        Stores the results of testcases inside the TestAction
        Call from subclasses before checking subclass-specific events.
        """
        ret_val = False
        if event == "eof":
            self.logger.warning("err: lava test monitoring reached end of file")
            self.errors = "lava test monitoring reached end of file"
            raise ConnectionClosedError("Connection closed")
        elif event == "timeout":
            self.logger.warning("err: lava test monitoring has timed out")
            self.errors = "lava test monitoring has timed out"
        elif event == "end":
            self.logger.info("ok: end string found, lava test monitoring stopped")
        elif event == "test_result":
            self.logger.info("ok: test case found")
            match = test_connection.match.groupdict()
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
                        self.logger.results(results)
                        self.report[case_id] = match["result"]
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
                        self.logger.results(results)
                        self.report[case_id] = "pass"
            ret_val = True
        return ret_val
