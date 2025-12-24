# Copyright (C) 2025 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.yaml import yaml_safe_dump

if TYPE_CHECKING:
    from lava_common.log import ResultDict, YAMLLogger


class ReportMixin:
    """Mixin providing extra test result reporting methods.

    It can only be used with 'Action' subclasses that:
    - initialize and populate the 'self.report' attr.
    - provide 'self.logger' and 'self.level' attrs.
    """

    report: dict[str, str | dict[str, str]]
    logger: YAMLLogger
    level: str

    def handle_expected(self, expected: list[str], suite: str) -> None:
        expected_set = set(expected)
        reported_set = set(self.report)

        if expected_set == reported_set:
            return

        if missing := expected_set - reported_set:
            self.logger.warning("Reporting missing expected test cases as 'fail' ...")
            for test_case_id in sorted(missing):
                res: ResultDict = {
                    "definition": suite,
                    "case": test_case_id,
                    "result": "fail",
                    "level": self.level,
                    "extra": {
                        "reason": "missing expected test cases are reported as 'fail' by LAVA."
                    },
                }
                self.report[test_case_id] = "fail"
                self.logger.results(res)

        for tc in sorted(reported_set - expected_set):
            self.logger.warning(f"Unexpected test result: {tc}: {self.report[tc]}")

    def handle_summary(self, suite: str) -> None:
        # Only print if the report is not empty
        if self.report:
            header = f"--- {suite} Test Report ---"
            footer = " End ".center(len(header), "-")
            self.logger.debug(header)
            self.logger.debug(yaml_safe_dump(self.report, default_flow_style=False))
            self.logger.debug(footer)
