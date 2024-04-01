# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import MagicMock, patch

import pexpect

from lava_dispatcher.actions.deploy.flasher import Flasher, FlasherAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.utils import DummyLogger


class FlasherFactory(Factory):
    def create_b2260_job(self, filename):
        job = super().create_job("b2260-01", filename)
        job.logger = DummyLogger()
        return job


class TestFlasher(LavaDispatcherTestCase):
    def test_pipeline(self):
        factory = FlasherFactory()
        job = factory.create_b2260_job("sample_jobs/b2260-flasher.yaml")
        job.validate()
        description_ref = self.pipeline_reference("b2260-flasher.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_run(self):
        class Proc:
            # pylint: disable=no-self-argument
            def wait(self_):
                return 0

            def expect(self_, arg):
                self.assertEqual(arg, pexpect.EOF)

            proc = MagicMock()

        commands = [
            ["/home/lava/bin/PiCtrl.py", "PowerPlug", "0", "off"],
            ["touch"],
        ]
        job = self.create_simple_job(
            device_dict={
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

        action = FlasherAction(job)
        action.parameters = {"namespace": "common", "images": {}}
        action.section = Flasher.section

        # self.commands is populated by validate
        action.validate()
        self.assertFalse(action.errors)

        # Run the action
        with patch(
            "lava_dispatcher.action.PexpectPopenSpawn", return_value=Proc()
        ) as mock_spawn:
            action.run(None, 10)

        self.assertEqual(mock_spawn.call_count, 2)

        for i, call in enumerate(mock_spawn.mock_calls):
            self.assertEqual(call.kwargs["cmd"], commands[i])
            self.assertEqual(call.kwargs["encoding"], "utf-8")
            self.assertEqual(call.kwargs["codec_errors"], "replace")
            self.assertEqual(call.kwargs["searchwindowsize"], 10)

    def test_accepts(self):
        # Normal case
        device = {"actions": {"deploy": {"methods": "flasher"}}}
        params = {"to": "flasher"}
        self.assertEqual(Flasher.accepts(device, params), (True, "accepted"))

        # Flasher is not defined
        device = {"actions": {"deploy": {"methods": "tftp"}}}
        params = {"to": "flasher"}
        self.assertEqual(
            Flasher.accepts(device, params),
            (False, "'flasher' not in the device configuration deploy methods"),
        )

        # Flasher is not requested
        device = {"actions": {"deploy": {"methods": "flasher"}}}
        params = {"to": "tftp"}
        self.assertEqual(
            Flasher.accepts(device, params), (False, '"to" parameter is not "flasher"')
        )
