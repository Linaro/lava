# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import MagicMock
from unittest.mock import call as mock_call

from lava_dispatcher.actions.commands import CommandAction
from lava_dispatcher.device import DeviceDict

from ..test_basic import LavaDispatcherTestCase


class TestCommands(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.job = self.create_simple_job(
            device_dict=DeviceDict(
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
        self.assertTrue(self.action.validate())

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
        self.assertFalse(self.action.validate())
        self.assertIn("Unknown user command 'unknown_command'", self.action.errors)

    def test_unconfigured_device(self):
        self.job.device = DeviceDict()
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
