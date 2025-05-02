# Copyright 2019-2024 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
#         Gopalakrishnan RAJINE ANAND <gopalakrishnan.rajineanand@nxp.com>
#         Larry Shen <larry.shen@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.actions.boot.uuu import (
    CheckSerialDownloadMode,
    UUUBootAction,
    UUUBootRetryAction,
)
from lava_dispatcher.job import Job
from lava_dispatcher.namespace_state import DownloadedFile
from lava_dispatcher.utils.containers import DockerDriver, NullDriver
from lava_dispatcher.utils.uuu import OptionalContainerUuuAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class UUUBootFactory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_imx8mq_job(self, device_template, filename):
        return self.create_job(device_template, filename)

    def create_imx8mq_job_uuu_path_from_command(self, filename):
        return self.create_job("imx8mq-evk-03.jinja2", filename)

    def create_imx8dxlevk_job(self, filename):
        return self.create_job("imx8dxl-evk-01.jinja2", filename)

    def create_imx8dxlevk_without_bcu_configuration_board_id(self, filename):
        return self.create_job("imx8dxl-evk-02.jinja2", filename)

    def create_imx8dxlevk_with_bcu_board_id_command(self, filename):
        return self.create_job("imx8dxl-evk-03.jinja2", filename)


@patch("time.sleep", Mock())
@patch("builtins.print", Mock())
@patch(
    "lava_dispatcher.utils.uuu.OptionalContainerUuuAction.which", Mock("/bin/test_uuu")
)
class TestCheckSerialDownloadMode(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = UUUBootFactory()

    def find_check_serial_action(self, job: Job) -> CheckSerialDownloadMode:
        action = job.pipeline.find_action(CheckSerialDownloadMode)
        action.parameters["namespace"] = "common"
        action.state.downloads["boot"] = DownloadedFile(file="file.boot")
        action.uuu = "/bin/uuu"
        action.linux_timeout = "/bin/timeout"
        action.maybe_copy_to_container = MagicMock()
        return action

    def test_check_board_availability_not_available(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-02.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = self.find_check_serial_action(job)
        action.run_uuu = MagicMock(return_value=143)

        self.assertEqual(False, action.check_board_availability())

    def test_check_board_availability_failure(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-02.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = self.find_check_serial_action(job)
        action.run_uuu = MagicMock(return_value=1)

        with self.assertRaises(InfrastructureError) as e:
            action.check_board_availability()

        self.assertEqual(
            "Fail UUUBootAction on cmd : /bin/timeout --preserve-status 10 /bin/uuu -m 1:14 file.boot",
            str(e.exception),
        )

    def test_check_board_availability_single_otg_path(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-02.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = self.find_check_serial_action(job)
        action.run_uuu = MagicMock(return_value=0)

        action.check_board_availability()
        action.run_uuu.assert_called_with(
            [
                "/bin/timeout",
                "--preserve-status",
                "10",
                "/bin/uuu",
                "-m",
                "1:14",
                "file.boot",
            ],
            allow_fail=True,
        )

    def test_check_board_availability_multiple_otg_path(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-01.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = self.find_check_serial_action(job)
        action.run_uuu = MagicMock(return_value=0)

        action.check_board_availability()
        action.run_uuu.assert_called_with(
            [
                "/bin/timeout",
                "--preserve-status",
                "10",
                "/bin/uuu",
                "-m",
                "2:143",
                "-m",
                "3:123",
                "file.boot",
            ],
            allow_fail=True,
        )

    def test_check_board_availability_single_otg_path_from_command(self):
        job = self.factory.create_imx8dxlevk_with_bcu_board_id_command(
            "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = self.find_check_serial_action(job)
        action.run_uuu = MagicMock(return_value=0)

        action.check_board_availability()
        action.run_uuu.assert_called_with(
            [
                "/bin/timeout",
                "--preserve-status",
                "10",
                "/bin/uuu",
                "-m",
                "12:123",
                "file.boot",
            ],
            allow_fail=True,
        )

    def test_check_board_availability_multiple_otg_path_from_command(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-03.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = self.find_check_serial_action(job)
        action.run_uuu = MagicMock(return_value=0)

        action.check_board_availability()
        action.run_uuu.assert_called_with(
            [
                "/bin/timeout",
                "--preserve-status",
                "10",
                "/bin/uuu",
                "-m",
                "12:1234",
                "-m",
                "1:1234",
                "file.boot",
            ],
            allow_fail=True,
        )

    def test_run_available(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-03.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = self.find_check_serial_action(job)
        action.check_board_availability = MagicMock(return_value=True)

        action.run(connection=None, max_end_time=None)

        self.assertTrue(action.state.uuu.otg_availability_check)

    def test_run_not_available(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-03.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = self.find_check_serial_action(job)
        action.check_board_availability = MagicMock(return_value=False)

        action.run(connection=None, max_end_time=None)

        self.assertFalse(action.state.uuu.otg_availability_check)


@patch("builtins.print", Mock())
@patch(
    "lava_dispatcher.utils.uuu.OptionalContainerUuuAction.which", Mock("/bin/test_uuu")
)
class TestUUUbootAction(
    LavaDispatcherTestCase
):  # pylint: disable=too-many-public-methods
    def setUp(self):
        super().setUp()
        self.factory = UUUBootFactory()

    def test_pipeline_uuu_only_uboot(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-01.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        self.assertIsNotNone(job)

        # Test that generated pipeline is the same as defined in pipeline_refs
        description_ref = self.pipeline_reference("uuu-bootimage-only.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

    def test_pipeline_power_off_before_corrupt_boot_media(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-02.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        self.assertIsNotNone(job)

        # Test that generated pipeline is the same as defined in pipeline_refs
        description_ref = self.pipeline_reference(
            "uuu-power-off-before-corrupt-boot-media.yaml", job=job
        )
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

    def test_pipeline_uuu_only_uboot_uuu_path_from_command(self):
        job = self.factory.create_imx8mq_job_uuu_path_from_command(
            "sample_jobs/uuu-bootimage-only.yaml"
        )
        self.assertIsNotNone(job)

        # Test that generated pipeline is the same as defined in pipeline_refs
        description_ref = self.pipeline_reference("uuu-bootimage-only.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

        # Test if uuu_otg_path have been updated before populating tasks
        uuu_boot_actions = list(
            filter(lambda e: isinstance(e, UUUBootRetryAction), job.pipeline.actions)
        )

        for uuu_boot_action in uuu_boot_actions:
            self.assertEqual(
                ["12:1234", "1:1234"],
                uuu_boot_action.job.device["actions"]["boot"]["methods"]["uuu"][
                    "options"
                ]["usb_otg_path"],
            )

    def test_pipeline_uuu_boot_action_bcu_configured(self):
        job = self.factory.create_imx8dxlevk_job("sample_jobs/uuu_enhancement.yaml")

        self.assertIsNotNone(job)

        # Test that generated pipeline is the same as defined in pipeline_refs
        description_ref = self.pipeline_reference("uuu-enhancement.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        self.assertIsNone(job.validate())

    def test_pipeline_action_boot_uuu_exception(self):
        with self.assertRaises(JobError) as cm:
            self.factory.create_imx8dxlevk_without_bcu_configuration_board_id(
                "sample_jobs/uuu_enhancement.yaml"
            )

        self.assertIsNotNone(cm.exception)
        self.assertIsInstance(cm.exception, Exception)
        self.assertEqual("Job", cm.exception.error_type)

        self.assertIsNotNone(cm.exception.args)
        self.assertIsInstance(cm.exception.args, tuple)
        self.assertTrue(len(cm.exception.args) >= 1)

        self.assertEqual(
            "bcu_board_id '' do not respect bcu format or 'bcu_board_id_command' not defined in device",
            cm.exception.args[0],
        )

    def test_pipeline_uuu_boot_action_imx8mq_for_bcu_exception(self):
        with self.assertRaises(JobError) as cm:
            self.factory.create_imx8mq_job_uuu_path_from_command(
                "sample_jobs/uuu_enhance_test.yaml"
            )

        self.assertIsNotNone(cm.exception)
        self.assertIsInstance(cm.exception, Exception)
        self.assertEqual("Job", cm.exception.error_type)

        self.assertIsNotNone(cm.exception.args)
        self.assertIsInstance(cm.exception.args, tuple)
        self.assertTrue(len(cm.exception.args) >= 1)

        self.assertEqual(
            "'bcu_board_name' is not defined in device-types",
            cm.exception.args[0],
        )

    def test_bcu_board_id_from_command(self):
        job = self.factory.create_imx8dxlevk_with_bcu_board_id_command(
            "sample_jobs/uuu_enhancement.yaml"
        )
        self.assertIsNotNone(job)

        # Test that generated pipeline is the same as defined in pipeline_refs
        description_ref = self.pipeline_reference("uuu-enhancement.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

        # Test if bcu_board_id have been updated before populating tasks
        uuu_boot_actions_for_bcu = list(
            filter(lambda e: isinstance(e, UUUBootRetryAction), job.pipeline.actions)
        )

        for uuu_boot_action_for_bcu in uuu_boot_actions_for_bcu:
            self.assertEqual(
                "2-1.3",
                uuu_boot_action_for_bcu.job.device["actions"]["boot"]["methods"]["uuu"][
                    "options"
                ]["bcu_board_id"],
            )

    def test_bcu_only(self):
        job = self.factory.create_imx8dxlevk_with_bcu_board_id_command(
            "sample_jobs/uuu_bcu_only.yaml"
        )
        self.assertIsNotNone(job)
        self.maxDiff = None
        # Test that generated pipeline is the same as defined in pipeline_refs
        description_ref = self.pipeline_reference("uuu-bcu-only.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

        # Test if bcu_board_id have been updated before populating tasks
        uuu_boot_actions_for_bcu = list(
            filter(lambda e: isinstance(e, UUUBootRetryAction), job.pipeline.actions)
        )

        for uuu_boot_action_for_bcu in uuu_boot_actions_for_bcu:
            self.assertEqual(
                "2-1.3",
                uuu_boot_action_for_bcu.job.device["actions"]["boot"]["methods"]["uuu"][
                    "options"
                ]["bcu_board_id"],
            )

    @patch("time.sleep", Mock())
    def test_run_single_path(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-02.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = job.pipeline.find_action(UUUBootAction)
        action.uuu = "/bin/uuu"

        action.state.uuu.uuu_images = ["boot"]
        action.state.downloads["boot"] = DownloadedFile(file="image.boot")

        action.parameters["commands"] = [{"uuu": "-b sd {boot}"}]

        action.run_uuu = MagicMock(return_value=0)
        action.run_bcu = MagicMock(return_value=0)
        action.cleanup_required = False

        action.run(connection=None, max_end_time=None)

        action.run_uuu.assert_called_with(
            ["/bin/uuu", "-m", "1:14", "-b", "sd", "image.boot"],
            allow_fail=False,
            error_msg="Fail UUUBootAction on cmd : -b sd image.boot",
        )

        action.cleanup(connection=None)
        action.run_bcu.assert_not_called()

    @patch("time.sleep", Mock())
    def test_run_single_path_with_bcu(self):
        job = self.factory.create_imx8dxlevk_job("sample_jobs/uuu_enhancement.yaml")
        action = job.pipeline.find_action(UUUBootAction)
        action.uuu = "/bin/uuu"
        action.bcu = "/bin/bcu"

        action.state.uuu.uuu_images = ["boot"]
        action.state.downloads["boot"] = DownloadedFile(file="image.boot")

        action.parameters["commands"] = [{"bcu": "reset usb"}, {"uuu": "-b sd {boot}"}]

        action.run_uuu = MagicMock(return_value=0)
        action.run_bcu = MagicMock(return_value=0)

        action.run(connection=None, max_end_time=None)

        action.run_bcu.assert_called_with(
            ["/bin/bcu", "reset", "usb", "-board=imx8dxlevk", "-id=2-1.3"],
            allow_fail=False,
            error_msg="Fail UUUBootAction on cmd : reset usb",
        )

        action.run_uuu.assert_called_with(
            ["/bin/uuu", "-m", "12:123", "-b", "sd", "image.boot"],
            allow_fail=False,
            error_msg="Fail UUUBootAction on cmd : -b sd image.boot",
        )

        action.cleanup(connection=None)
        action.run_bcu.assert_called_with(
            ["/bin/bcu", "deinit", "-board=imx8dxlevk", "-id=2-1.3"],
            allow_fail=False,
            error_msg="Fail UUUBootAction on cmd : deinit",
        )

    @patch("time.sleep", Mock())
    def test_run_multiple_path(self):
        job = self.factory.create_imx8mq_job(
            "imx8mq-evk-01.jinja2", "sample_jobs/uuu-bootimage-only.yaml"
        )
        action = job.pipeline.find_action(UUUBootAction)
        action.uuu = "/bin/uuu"

        action.state.uuu.uuu_images = ["boot"]
        action.state.downloads["boot"] = DownloadedFile(file="image.boot")

        action.parameters["commands"] = [{"uuu": "-b sd {boot}"}]

        action.run_uuu = MagicMock(return_value=0)

        action.run(connection=None, max_end_time=None)

        action.run_uuu.assert_called_with(
            ["/bin/uuu", "-m", "2:143", "-m", "3:123", "-b", "sd", "image.boot"],
            allow_fail=False,
            error_msg="Fail UUUBootAction on cmd : -b sd image.boot",
        )

    def test_pipeline_skip_uuu(self):
        job = self.factory.create_imx8dxlevk_with_bcu_board_id_command(
            "sample_jobs/uuu_skip.yaml"
        )
        self.assertIsNotNone(job)

        # Test that generated pipeline is the same as defined in pipeline_refs
        description_ref = self.pipeline_reference("uuu-skip.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())


class TestUUUActionDriver(LavaDispatcherTestCase):
    def create_action(self, uuu_device_parameters):
        action = OptionalContainerUuuAction(
            self.create_simple_job(job_parameters={"dispatcher": {}})
        )
        action.parameters["namespace"] = "common"
        action.job.device = {
            "actions": {
                "boot": {"methods": {"uuu": {"options": uuu_device_parameters}}}
            }
        }
        return action

    def test_uuu_null_driver(self):
        uuu_device_parameters = {"docker_image": "", "remote_options": ""}
        action = self.create_action(uuu_device_parameters)
        self.assertIsInstance(action.driver, NullDriver)

    def test_uuu_docker_driver(self):
        uuu_device_parameters = {
            "docker_image": "atline/uuu:1.3.191",
            "remote_options": "",
        }
        action = self.create_action(uuu_device_parameters)
        self.assertIsInstance(action.driver, DockerDriver)

    @patch.object(OptionalContainerUuuAction, "run_cmd")
    def test_native_uuu_cmd(self, mock_cmd):
        uuu_device_parameters = {"docker_image": "", "remote_options": ""}
        action = self.create_action(uuu_device_parameters)
        action.run_uuu(["foo", "bar"])
        mock_cmd.assert_called_with(["foo", "bar"], False, None, None)

    @patch.object(OptionalContainerUuuAction, "run_cmd")
    def test_docker_uuu_local_cmd(self, mock_cmd):
        uuu_device_parameters = {
            "docker_image": "atline/uuu:1.3.191",
            "remote_options": "",
        }
        action = self.create_action(uuu_device_parameters)
        action.run_uuu(["foo", "bar"])
        mock_cmd.assert_called_with(
            [
                "docker",
                "run",
                "-t",
                "--privileged",
                "--volume=/dev:/dev",
                "--net=host",
                "--rm",
                "--init",
                "atline/uuu:1.3.191",
                "foo",
                "bar",
            ],
            False,
            None,
            None,
        )

    @patch("lava_dispatcher.utils.uuu.dispatcher_ip", return_value="foo")
    @patch.object(OptionalContainerUuuAction, "run_cmd")
    def test_docker_uuu_remote_cmd(self, mock_cmd, mock_ip):
        uuu_device_parameters = {
            "docker_image": "atline/uuu:1.3.191",
            "remote_options": "--tlsverify --tlscacert=/labScripts/remote_cert/ca.pem --tlscert=/labScripts/remote_cert/cert.pem --tlskey=/labScripts/remote_cert/key.pem -H 10.192.244.5:2376",
        }
        action = self.create_action(uuu_device_parameters)
        action.state.uuu.root_location = "bar"
        action.run_uuu(["foo", "bar"])
        mock_cmd.assert_called_with(
            [
                "docker",
                "--tlsverify",
                "--tlscacert=/labScripts/remote_cert/ca.pem",
                "--tlscert=/labScripts/remote_cert/cert.pem",
                "--tlskey=/labScripts/remote_cert/key.pem",
                "-H",
                "10.192.244.5:2376",
                "run",
                "-t",
                "--privileged",
                "--volume=/dev:/dev",
                "--net=host",
                "--rm",
                "--init",
                "atline/uuu:1.3.191",
                "bash",
                "-c",
                "mkdir -p bar && mount -t nfs -o nolock foo:bar bar && foo bar",
            ],
            False,
            None,
            None,
        )

    @patch.object(OptionalContainerUuuAction, "run_cmd")
    @patch("lava_dispatcher.utils.docker.DockerRun.__check_image_arch__")
    def test_docker_uuu_local_validate(self, _, mock_cmd):
        uuu_device_parameters = {
            "docker_image": "atline/uuu:1.3.191",
            "remote_options": "",
        }
        action = self.create_action(uuu_device_parameters)
        action.driver.validate()
        mock_cmd.assert_called_with(["docker", "pull", "atline/uuu:1.3.191"])

    @patch.object(OptionalContainerUuuAction, "run_cmd")
    @patch("lava_dispatcher.utils.docker.DockerRun.__check_image_arch__")
    def test_docker_uuu_remote_validate(self, _, mock_cmd):
        uuu_device_parameters = {
            "docker_image": "atline/uuu:1.3.191",
            "remote_options": "--tlsverify --tlscacert=/labScripts/remote_cert/ca.pem --tlscert=/labScripts/remote_cert/cert.pem --tlskey=/labScripts/remote_cert/key.pem -H 10.192.244.5:2376",
        }
        action = self.create_action(uuu_device_parameters)
        action.driver.validate()
        mock_cmd.assert_called_with(
            [
                "docker",
                "--tlsverify",
                "--tlscacert=/labScripts/remote_cert/ca.pem",
                "--tlscert=/labScripts/remote_cert/cert.pem",
                "--tlskey=/labScripts/remote_cert/key.pem",
                "-H",
                "10.192.244.5:2376",
                "pull",
                "atline/uuu:1.3.191",
            ]
        )
