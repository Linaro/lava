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

import os
import pytest  # pylint: disable=unused-import
import select
import subprocess  # nosec - unit tests

from lava_dispatcher.device import NewDevice, PipelineDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.tests.test_basic import Factory, StdoutTestCase
from lava_dispatcher.tests.utils import DummyLogger
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.deploy.flasher import Flasher, FlasherAction
from lava_dispatcher.job import Job

# This will be monkey patched
import lava_dispatcher.utils.shell  # pylint: disable=unused-import
import lava_dispatcher.actions.deploy.docker  # pylint: disable=unused-import


class FlasherFactory(Factory):
    def create_b2260_job(self, filename):
        # FIXME: b2260 Jinja2 template does not have flasher support.
        device = NewDevice(
            os.path.join(os.path.dirname(__file__), "../devices/b2260-01.yaml")
        )
        with open(os.path.join(os.path.dirname(__file__), filename)) as f_in:
            parser = JobParser()
            job = parser.parse(f_in, device, 456, None, "")
        job.logger = DummyLogger()
        return job


class TestFlasher(StdoutTestCase):
    def test_pipeline(self):
        factory = FlasherFactory()
        job = factory.create_b2260_job("sample_jobs/b2260-flasher.yaml")
        job.validate()
        description_ref = self.pipeline_reference("b2260-flasher.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))


def test_run(monkeypatch):
    class FD:
        def readlines(self):
            return []

    class Proc:
        def __init__(self):
            self.stderr = FD()
            self.stdout = FD()

        def poll(self):
            return 0

        def wait(self):
            return 0

    class Poller:
        def register(self, fd, flag):
            pass

    commands = [
        ["nice", "/home/lava/bin/PiCtrl.py", "PowerPlug", "0", "off"],
        ["nice", "touch"],
    ]

    def Popen(
        cmd, cwd, stdout, stderr, bufsize, universal_newlines
    ):  # nosec - unit test
        assert cmd == commands.pop(0)  # nosec - unit test
        assert stdout == subprocess.PIPE  # nosec - unit test
        assert stderr == subprocess.PIPE  # nosec - unit test
        assert bufsize == 1  # nosec - unit test
        assert universal_newlines  # nosec - unit test
        return Proc()

    monkeypatch.setattr(subprocess, "Popen", Popen)
    monkeypatch.setattr(select, "epoll", lambda: Poller())

    action = FlasherAction()
    device = PipelineDevice(
        {
            "actions": {
                "deploy": {
                    "methods": {
                        "flasher": {"commands": ["{HARD_RESET_COMMAND}", "touch"]}
                    }
                }
            },
            "commands": {"hard_reset": "/home/lava/bin/PiCtrl.py PowerPlug 0 off"},
        }
    )
    action.job = Job(1234, {}, None)
    action.job.device = device
    action.parameters = {"namespace": "common", "images": {}}
    action.section = Flasher.action_type

    # self.commands is populated by validate
    action.validate()
    assert action.errors == []  # nosec - unit test

    # Run the action
    action.run(None, 10)
    assert commands == []  # nosec - unit test


def test_accepts():
    pipe = Pipeline(job=Job(1234, {}, None))
    pipe.add_action = lambda a, b: None
    flasher = Flasher(pipe, {})

    # Normal case
    device = {"actions": {"deploy": {"methods": "flasher"}}}
    params = {"to": "flasher"}
    assert flasher.accepts(device, params) == (True, "accepted")  # nosec - unit test

    # Flasher is not defined
    device = {"actions": {"deploy": {"methods": "tftp"}}}
    params = {"to": "flasher"}
    assert flasher.accepts(device, params) == (  # nosec - unit test
        False,
        "'flasher' not in the device configuration deploy methods",
    )

    # Flasher is not requested
    device = {"actions": {"deploy": {"methods": "flasher"}}}
    params = {"to": "tftp"}
    assert flasher.accepts(device, params) == (  # nosec - unit test
        False,
        '"to" parameter is not "flasher"',
    )
