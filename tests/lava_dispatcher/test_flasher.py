# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import shlex

import pexpect

import lava_dispatcher.actions.deploy.docker  # pylint: disable=unused-import

# This will be monkey patched
import lava_dispatcher.utils.shell  # pylint: disable=unused-import
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.deploy.flasher import Flasher, FlasherAction
from lava_dispatcher.device import PipelineDevice
from lava_dispatcher.job import Job
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import DummyLogger


class FlasherFactory(Factory):
    def create_b2260_job(self, filename):
        job = super().create_job("b2260-01.jinja2", filename)
        job.logger = DummyLogger()
        return job


class TestFlasher(StdoutTestCase):
    def test_pipeline(self):
        factory = FlasherFactory()
        job = factory.create_b2260_job("sample_jobs/b2260-flasher.yaml")
        job.validate()
        description_ref = self.pipeline_reference("b2260-flasher.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())


def test_run(monkeypatch):
    class Proc:
        def wait(self):
            return 0

        def expect(self, arg):
            assert arg == pexpect.EOF

    commands = [
        ["/home/lava/bin/PiCtrl.py", "PowerPlug", "0", "off"],
        ["touch"],
    ]

    def spawn(cmd, cwd, encoding, codec_errors, logfile, timeout, searchwindowsize):
        command = commands.pop(0)
        assert cmd == shlex.join(command)
        assert encoding == "utf-8"
        assert codec_errors == "replace"
        assert searchwindowsize == 10
        return Proc()

    monkeypatch.setattr(pexpect, "spawn", spawn)

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
    action.section = Flasher.section

    # self.commands is populated by validate
    action.validate()
    assert action.errors == []  # nosec - unit test

    # Run the action
    action.run(None, 10)
    assert commands == []  # nosec - unit test


def test_accepts():
    pipe = Pipeline(job=Job(1234, {}, None))
    pipe.add_action = lambda a, b: None
    flasher = Flasher

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
