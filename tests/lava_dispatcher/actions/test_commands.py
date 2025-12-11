# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import MagicMock
from unittest.mock import call as mock_call
from unittest.mock import patch

from lava_dispatcher.actions.commands import CommandAction
from lava_dispatcher.device import PipelineDevice

from ..test_basic import LavaDispatcherTestCase


class TestCommands(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.job = self.create_simple_job(
            device_dict=PipelineDevice(
                {
                    "commands": {
                        "hard_reset": "/path/to/hard-reset",
                        "power_off": ["something", "something-else"],
                        "users": {
                            "do_something": {"do": "/bin/do", "undo": "/bin/undo"}
                        },
                    }
                }
            )
        )
        self.action = CommandAction(self.job)
        self.action.run_cmd = MagicMock()

    def do_something(self):
        self.action.parameters = {"name": "do_something"}
        self.action.validate()
        self.assertTrue(self.action.valid)

    def hard_reset(self):
        self.action.parameters = {"name": "hard_reset"}
        self.action.validate()

    def test_run(self):
        self.do_something()
        self.action.run(None, 600)
        self.action.run_cmd.assert_called_with("/bin/do")

    def test_cleanup(self):
        self.do_something()
        self.action.run(None, 600)
        self.action.cleanup(None)
        self.action.run_cmd.assert_called_with("/bin/undo")

    def test_unknown_command(self):
        self.action.parameters = {"name": "unknown_command"}
        self.action.validate()
        self.assertFalse(self.action.valid)
        self.assertEqual(["Unknown user command 'unknown_command'"], self.action.errors)

    def test_unconfigured_device(self):
        self.job.device = PipelineDevice({})
        self.action.parameters = {"name": "some-action"}
        self.assertFalse(self.action.validate())

    def test_builtin_command_run(self):
        self.hard_reset()
        self.action.run(None, 600)
        self.action.run_cmd.assert_called_with("/path/to/hard-reset")

    def test_builtin_command_cleanup_is_noop(self):
        self.hard_reset()
        self.action.run(None, 600)
        self.action.run_cmd.reset_mock()
        self.action.cleanup(None)
        self.action.run_cmd.assert_not_called()

    def test_builtin_command_not_defined_for_device(self):
        self.action.parameters = {"name": "pre_power_command"}
        self.assertFalse(self.action.validate())

    def test_multiple_commands(self):
        self.action.parameters = {"name": "power_off"}
        self.action.validate()
        self.action.run(None, 600)
        self.action.run_cmd.assert_has_calls(
            (mock_call("something"), mock_call("something-else"))
        )

    def test_usbg_ms_commands_disable(self):
        self.job.device = PipelineDevice(
            {
                "actions": {
                    "deploy": {
                        "methods": {
                            "usbg-ms": {"disable": ["laacli", "usbg-ms", "off"]}
                        }
                    }
                }
            }
        )
        self.action.parameters = {"name": "usbg_ms_commands_disable"}
        self.action.validate()
        self.assertTrue(self.action.valid)
        self.assertEqual({"do": "laacli usbg-ms off"}, self.action.cmd)
        self.action.run(None, 600)
        self.action.run_cmd.assert_called_with("laacli usbg-ms off")

    def test_usbg_ms_commands_disable_missing(self):
        self.job.device = PipelineDevice({})
        self.action.parameters = {"name": "usbg_ms_commands_disable"}
        self.action.validate()
        self.assertFalse(self.action.valid)
        self.assertEqual(
            ["Command 'usbg_ms_commands.disable' not defined for this device"],
            self.action.errors,
        )

    def test_stop_test_services(self):
        self.action.parameters = {"name": "stop_test_services"}
        stop_cmd = ["docker-compose", "-f", "/abs_path/docker-compose.yaml", "down"]

        with patch(
            "lava_dispatcher.actions.commands.CommandAction.get_namespace_data",
            return_value=[stop_cmd],
        ):
            self.action.validate()

        self.assertTrue(self.action.valid)
        self.assertEqual({"do": [stop_cmd]}, self.action.cmd)
        self.action.run(None, 600)
        self.action.run_cmd.assert_called_with(stop_cmd)

    def test_stop_test_services_missing(self):
        self.action.parameters = {"name": "stop_test_services"}
        with patch(
            "lava_dispatcher.actions.commands.CommandAction.get_namespace_data",
            return_value=None,
        ):
            self.action.validate()

        self.assertFalse(self.action.valid)
        self.assertEqual(
            [
                "Command for 'stop_test_services' not found. No 'test.services' action defined?"
            ],
            self.action.errors,
        )
