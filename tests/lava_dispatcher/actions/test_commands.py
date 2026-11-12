# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from unittest.mock import call as mock_call

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.actions.commands import CommandAction
from lava_dispatcher.actions.deploy.overlay import CreateOverlay
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
                            "do_something": {"do": "/bin/do", "undo": "/bin/undo"},
                            "secret_command": {
                                "do": "echo mysecret!",
                                "undo": "/bin/undo",
                            },
                            "empty_command": {"do": "echo -n ''"},
                            "reuse_secret": {
                                "do": "bash -c 'echo $TEST_CREATE_SECRET'"
                            },
                            "bad_command": {"do": "bash -c 'exit 1'"},
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

    def test_usbg_ms_commands_disable(self):
        self.job.device = DeviceDict(
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
        self.job.device = DeviceDict()
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

    def test_command_create_secret(self):
        self.addCleanup(os.environ.pop, "TEST_CREATE_SECRET", None)
        self.action.parameters = {
            "name": "secret_command",
            "create_secret": "TEST_CREATE_SECRET",
        }
        self.action.validate()
        self.action.run(None, 600)
        self.assertEqual(self.job.secrets.get("TEST_CREATE_SECRET"), "mysecret!")
        self.assertEqual(os.environ["TEST_CREATE_SECRET"], "mysecret!")
        self.assertIn("mysecret!", self.job.logger.secrets_mask)

    def test_command_bad_command_with_secret(self):
        self.action.parameters = {
            "name": "bad_command",
            "create_secret": "BAD_COMMAND_SECRET",
        }
        self.action.validate()
        with self.assertRaises(InfrastructureError):
            self.action.run(None, 600)

    def test_command_secret_available_to_later_command(self):
        self.addCleanup(os.environ.pop, "TEST_CREATE_SECRET", None)
        self.addCleanup(os.environ.pop, "TEST_REUSED_SECRET", None)
        self.action.parameters = {
            "name": "secret_command",
            "create_secret": "TEST_CREATE_SECRET",
        }
        self.action.validate()
        self.action.run(None, 600)

        # a later command action in the same job can use the new secret
        later_action = CommandAction(self.job)
        later_action.parameters = {
            "name": "reuse_secret",
            "create_secret": "TEST_REUSED_SECRET",
        }
        later_action.validate()
        later_action.run(None, 600)
        self.assertEqual(self.job.secrets.get("TEST_REUSED_SECRET"), "mysecret!")

    def test_command_secret_no_output(self):
        self.action.parameters = {
            "name": "empty_command",
            "create_secret": "EMPTY_SECRET",
        }
        self.action.validate()
        self.action.run(None, 600)
        self.assertIsNone(self.job.secrets.get("EMPTY_SECRET"))
        self.assertNotIn("EMPTY_SECRET", os.environ)

    def test_secret_command_undo_uses_run_cmd(self):
        # create_secret changes the do path only; cleanup still runs
        # the undo command via run_cmd
        self.addCleanup(os.environ.pop, "TEST_CREATE_SECRET", None)
        self.action.parameters = {
            "name": "secret_command",
            "create_secret": "TEST_CREATE_SECRET",
        }
        self.action.validate()
        self.action.run(None, 600)
        self.action.run_cmd.reset_mock()
        self.action.cleanup(None)
        self.action.run_cmd.assert_called_with("/bin/undo")


class TestCommandSecretOverlay(LavaDispatcherTestCase):
    def test_created_secret_written_to_overlay(self):
        self.addCleanup(os.environ.pop, "TEST_OVERLAY_SECRET", None)
        job = self.create_simple_job(
            device_dict={
                "constants": {
                    "posix": {
                        "lava_test_results_dir": "/lava-%s",
                        "lava_test_sh_cmd": "/bin/sh",
                    }
                },
                "actions": {"deploy": {"methods": {}}},
                "commands": {"users": {"secret_command": {"do": "echo mysecret!"}}},
            },
            job_parameters={"dispatcher": {"dispatcher_ip": "192.0.2.1"}},
        )

        command = CommandAction(job)
        command.parameters = {
            "name": "secret_command",
            "create_secret": "TEST_OVERLAY_SECRET",
        }
        command.validate()
        command.run(None, 600)

        # the overlay of a later deploy action exports the new secret to the DUT
        overlay = CreateOverlay(job)
        overlay.parameters = {"namespace": "common"}
        with TemporaryDirectory(prefix="overlay-secrets-") as tmp_dir:
            with patch.object(job, "mkdtemp", return_value=tmp_dir):
                overlay.validate()
                overlay.run(None, None)
            secrets = (Path(tmp_dir) / f"lava-{job.job_id}" / "secrets").read_text()

        self.assertIn("TEST_OVERLAY_SECRET='mysecret!'", secrets.splitlines())


class TestCommandSecretGuards(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.job = self.create_simple_job(
            device_dict=DeviceDict(
                {
                    "commands": {
                        # device builtins, like real device dicts have
                        "power_off": ["/bin/true", "/bin/false"],
                        "hard_reset": "echo reset-value",
                        "users": {
                            "multiline_command": {"do": "printf 'one\\ntwo\\n'"},
                            "multi_command": {"do": ["/bin/true", "/bin/true"]},
                            "single_command": {"do": "/bin/true"},
                            "leaky_command": {
                                "do": "bash -c 'echo \"$LEAK_SRC\"; exit 1'"
                            },
                        },
                    }
                }
            )
        )
        self.action = CommandAction(self.job)
        self.action.run_cmd = MagicMock()

    def test_multiline_secret_output_rejected(self):
        self.action.parameters = {
            "name": "multiline_command",
            "create_secret": "MULTILINE_SECRET",
        }
        self.action.validate()
        with self.assertRaises(JobError):
            self.action.run(None, 600)

    def test_multi_command_list_rejected(self):
        self.action.parameters = {
            "name": "multi_command",
            "create_secret": "LIST_SECRET",
        }
        with self.assertRaises(JobError):
            self.action.validate()

    def test_invalid_secret_name_rejected(self):
        self.action.parameters = {
            "name": "single_command",
            "create_secret": "bad-name",
        }
        with self.assertRaises(JobError) as ctx:
            self.action.validate()
        # user typo => "Job" (fix your job), not "Bug" (report to maintainers)
        self.assertEqual(ctx.exception.error_type, "Job")

    def test_secret_name_with_slash_rejected(self):
        self.action.parameters = {
            "name": "single_command",
            "create_secret": "bad/name",
        }
        with self.assertRaises(JobError):
            self.action.validate()

    def test_path_secret_rejected(self):
        # os.environ["PATH"] = <secret> would break every later command
        self.action.parameters = {
            "name": "single_command",
            "create_secret": "PATH",
        }
        with self.assertRaises(JobError):
            self.action.validate()

    def test_lava_prefixed_secret_rejected(self):
        # LAVA_* is the job environment namespace: clobbering e.g. LAVA_TOKEN
        # silently breaks the results upload mid-job
        self.action.parameters = {
            "name": "single_command",
            "create_secret": "LAVA_TOKEN",
        }
        with self.assertRaises(JobError):
            self.action.validate()

    def test_non_ascii_secret_name_rejected(self):
        # isidentifier() would accept this; not a usable env var name
        self.action.parameters = {
            "name": "single_command",
            "create_secret": "密钥",
        }
        with self.assertRaises(JobError):
            self.action.validate()

    def test_failed_secret_command_hides_output(self):
        action = CommandAction(self.job)
        action.parameters = {
            "name": "leaky_command",
            "create_secret": "LEAKY_SECRET",
        }
        action.validate()
        # the would-be secret exists only in the command's output, like a
        # failing `curl` of a token endpoint
        os.environ["LEAK_SRC"] = "supersecretvalue"
        self.addCleanup(os.environ.pop, "LEAK_SRC", None)
        # capture everything the job logger emits (what gets uploaded)
        capture = MagicMock()
        self.job.logger.handlers.append(capture)
        self.addCleanup(self.job.logger.handlers.remove, capture)
        with self.assertRaises(InfrastructureError):
            action.run(None, 600)
        emitted = " ".join(str(c) for c in capture.emit.call_args_list)
        # the failed generator must not leak its output into the log
        # uploaded to the scheduler, nor into the recorded results
        self.assertNotIn("supersecretvalue", emitted)
        self.assertNotIn("supersecretvalue", str(action.errors))
        self.assertNotIn("supersecretvalue", str(action.results))

    def test_builtin_list_command_rejected(self):
        # builtins may be a list and validate() returns early for them:
        # the guards must still apply, as command.md promises
        self.action.parameters = {
            "name": "power_off",
            "create_secret": "BUILTIN_SECRET",
        }
        with self.assertRaises(JobError):
            self.action.validate()

    def test_invalid_name_rejected_for_builtin(self):
        self.action.parameters = {
            "name": "power_off",
            "create_secret": "bad-name",
        }
        with self.assertRaises(JobError):
            self.action.validate()

    def test_builtin_scalar_command_allowed(self):
        # the supported builtin combination: single scalar command
        self.action.parameters = {
            "name": "hard_reset",
            "create_secret": "BUILTIN_SECRET",
        }
        self.action.validate()
        self.assertTrue(self.action.valid)
        self.addCleanup(os.environ.pop, "BUILTIN_SECRET", None)
        self.action.run(None, 600)
        self.assertEqual(self.job.secrets.get("BUILTIN_SECRET"), "reset-value")
