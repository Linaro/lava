# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import pytest
import subprocess  # nosec - only for mocking
import time

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.actions.test.interactive import TestInteractiveAction

from lava_dispatcher.tests.test_basic import Factory, StdoutTestCase

# This will be monkey patched
import lava_dispatcher.actions.deploy.docker


class InteractiveFactory(Factory):
    def create_interactive_job(self, device, filename):
        return self.create_job(device, filename)


def test_pipeline():
    factory = InteractiveFactory()
    job = factory.create_interactive_job(
        "b2260-01.jinja2", "sample_jobs/b2260-interactive.yaml"
    )
    job.validate()
    description_ref = StdoutTestCase.pipeline_reference(
        "b2260-interactive.yaml", job=job
    )
    assert description_ref == job.pipeline.describe(False)  # nosec


def test_stages(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda cmd: b"")
    monkeypatch.setattr(
        lava_dispatcher.actions.deploy.docker, "which", lambda a: "/usr/bin/docker"
    )
    factory = InteractiveFactory()
    job = factory.create_interactive_job(
        "docker-01.jinja2", "sample_jobs/docker-interactive.yaml"
    )
    job.validate()
    description_ref = StdoutTestCase.pipeline_reference(
        "docker-interactive.yaml", job=job
    )
    assert description_ref == job.pipeline.describe(False)  # nosec
    assert (  # nosec  - assert is part of the test process.
        job.pipeline.actions[3].internal_pipeline.actions[0].parameters["stage"] == 0
    )


def test_raise_exception():
    action = TestInteractiveAction()
    action.validate()

    with pytest.raises(InfrastructureError) as exc:
        action.raise_exception("InfrastructureError", "hello")
    assert exc.match("hello")  # nosec - assert is part of the test process.

    with pytest.raises(JobError) as exc:
        action.raise_exception("JobError", "A strange error")
    assert exc.match("A strange error")  # nosec - assert is part of the test process.

    with pytest.raises(JobError) as exc:
        action.raise_exception("bug", "A strange error")
    assert exc.match(  # nosec - assert is ok
        "Unknow exception 'bug' with 'A strange error'"
    )


class Connection:
    def __init__(self, data):
        self.data = data

    def sendline(self, line, delay):
        assert self.data.pop(0) == ("sendline", line)  # nosec - assert is ok

    def expect(self, expect, timeout=1):
        data = self.data.pop(0)
        assert (data[0], data[1]) == ("expect", expect)  # nosec - assert is ok
        return data[2]


class Logger:
    def __init__(self, data):
        self.data = data

    def debug(self, line, *args):
        assert self.data.pop(0) == ("debug", line % args)  # nosec - assert is ok

    def error(self, line, *args):
        assert self.data.pop(0) == ("error", line % args)  # nosec - assert is ok

    def info(self, line, *args):
        assert self.data.pop(0) == ("info", line % args)  # nosec - assert is ok

    def results(self, res):
        assert self.data.pop(0) == ("results", res)  # nosec - assert is ok


class Timing:
    def __init__(self):
        self.clock = 0

    def __call__(self):
        self.clock += 1
        return self.clock


def test_run_script(monkeypatch):
    monkeypatch.setattr(time, "time", Timing())
    action = TestInteractiveAction()
    action.parameters = {"stage": 0}
    action.logger = Logger(
        [
            ("info", "Sending nothing, waiting"),
            ("debug", "Waiting for '=> ', '/ # '"),
            ("debug", "Matched a prompt: '=> '"),
            (
                "results",
                {
                    "definition": "0_setup",
                    "case": "wait prompt",
                    "result": "pass",
                    "duration": "1.00",
                },
            ),
            ("info", "Sending 'help'"),
            ("debug", "Waiting for '=> ', '/ # '"),
            ("debug", "Matched a prompt: '=> '"),
            (
                "results",
                {
                    "definition": "0_setup",
                    "case": "network.help",
                    "result": "pass",
                    "duration": "1.00",
                },
            ),
            ("info", "Sending 'dhcp'"),
            ("debug", "Waiting for '=> ', '/ # ', 'DHCP client bound to address'"),
            ("info", "Matched a success: 'DHCP client bound to address'"),
            (
                "results",
                {
                    "definition": "0_setup",
                    "case": "network.dhcp",
                    "result": "pass",
                    "duration": "1.00",
                },
            ),
            ("info", "Sending 'host lavasoftware.org'"),
            (
                "debug",
                "Waiting for '=> ', '/ # ', 'Host lavasoftware.org not found: 3(NXDOMAIN)', 'TIMEOUT'",
            ),
            (
                "error",
                "Matched a failure: 'Host lavasoftware.org not found: 3(NXDOMAIN)'",
            ),
            (
                "results",
                {
                    "definition": "0_setup",
                    "case": "network.host",
                    "result": "fail",
                    "duration": "1.00",
                },
            ),
            ("info", "Sending 'ping -c 1 lavasoftware.org'"),
            ("debug", "Waiting for '=> ', '/ # ', 'Name or service not known'"),
            ("error", "Matched a failure: 'Name or service not known'"),
            (
                "results",
                {
                    "definition": "0_setup",
                    "case": "network.ping",
                    "result": "fail",
                    "duration": "1.00",
                },
            ),
        ]
    )
    action.validate()

    conn_data = [
        ("expect", ["=> ", "/ # "], 0),
        ("sendline", "help"),
        ("expect", ["=> ", "/ # "], 0),
        ("sendline", "dhcp"),
        ("expect", ["=> ", "/ # ", "DHCP client bound to address"], 2),
        ("expect", ["=> ", "/ # "], 0),
        ("sendline", "host lavasoftware.org"),
        (
            "expect",
            ["=> ", "/ # ", "Host lavasoftware.org not found: 3(NXDOMAIN)", "TIMEOUT"],
            2,
        ),
        ("sendline", "ping -c 1 lavasoftware.org"),
        ("expect", ["=> ", "/ # ", "Name or service not known"], 2),
    ]
    script = {
        "prompts": ["=> ", "/ # "],
        "name": "setup",
        "script": [
            {"command": None, "name": "wait prompt"},
            {"command": "help", "name": "network.help"},
            {
                "command": "dhcp",
                "name": "network.dhcp",
                "patterns": [
                    {"message": "DHCP client bound to address", "result": "success"}
                ],
            },
            {
                "command": "host {HOST}",
                "name": "network.host",
                "patterns": [
                    {
                        "message": "Host lavasoftware.org not found: 3(NXDOMAIN)",
                        "result": "failure",
                    },
                    {"message": "TIMEOUT", "result": "failure"},
                ],
            },
            {
                "command": "ping -c 1 {HOST}",
                "name": "network.ping",
                "patterns": [
                    {
                        "message": "Name or service not known",
                        "result": "failure",
                        "exception": "InfrastructureError",
                        "error": "network setup failed",
                    }
                ],
            },
        ],
    }
    test_connection = Connection(conn_data)
    substitutions = {"{HOST}": "lavasoftware.org"}
    with pytest.raises(InfrastructureError) as exc:
        action.run_script(test_connection, script, substitutions)
    assert exc.match(  # nosec - assert is part of the test process.
        "network setup failed"
    )
    assert action.logger.data == []  # nosec - assert is part of the test process.
    assert test_connection.data == []  # nosec - assert is part of the test process.
