# Copyright (C) 2023-present Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from importlib.util import find_spec
from unittest import SkipTest
from unittest.mock import ANY, call, patch

from lava_common.exceptions import JobError
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase

if find_spec("avh_api") is None:
    raise SkipTest("AVH is not installed.")

# pylint: disable=wrong-import-position
from avh_api.model.image import Image
from avh_api.model.instance_console_endpoint import InstanceConsoleEndpoint
from avh_api.model.instance_return import InstanceReturn
from avh_api.model.instance_state import InstanceState
from avh_api.model.model import Model
from avh_api.model.project import Project
from avh_api.model.token import Token

from lava_dispatcher.actions.boot.avh import BootAvh
from lava_dispatcher.actions.deploy.avh import Avh


def test_accepts_deploy():
    avh = Avh
    device = {"actions": {"deploy": {"methods": "avh"}}}
    params = {"to": "avh"}
    assert avh.accepts(device, params) == (
        True,
        "accepted",
    )

    device = {"actions": {"deploy": {"methods": "tftp"}}}
    params = {"to": "avh"}
    assert avh.accepts(device, params) == (
        False,
        "'avh' not in the device configuration deploy methods",
    )

    device = {"actions": {"deploy": {"methods": "avh"}}}
    params = {"to": "tftp"}
    assert avh.accepts(device, params) == (
        False,
        "'to' parameter is not 'avh'",
    )


def test_accepts_boot():
    boot_avh = BootAvh
    device = {"actions": {"boot": {"methods": "avh"}}}
    params = {"method": "avh"}
    assert boot_avh.accepts(device, params) == (
        True,
        "accepted",
    )

    device = {"actions": {"boot": {"methods": "tftp"}}}
    params = {"method": "avh"}
    assert boot_avh.accepts(device, params) == (
        False,
        "'avh' not in the device configuration boot methods",
    )

    device = {"actions": {"boot": {"methods": "avh"}}}
    params = {"method": "tftp"}
    assert boot_avh.accepts(device, params) == (
        False,
        "'method' is not 'avh'",
    )


class TestAvhActions(LavaDispatcherTestCase):
    def setUp(self, job="sample_jobs/avh-rpi4b.yaml"):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job("avh-01", job)

    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_pipeline(self):
        description_ref = self.pipeline_reference("avh-rpi4b.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    # Test deploy run.
    @patch("lava_dispatcher.actions.deploy.avh.Action.run")
    @patch("lava_dispatcher.actions.deploy.avh.random.choice", return_value="r")
    @patch("lava_dispatcher.actions.deploy.avh.zipfile.ZipFile.write")
    @patch("lava_dispatcher.actions.deploy.avh.zipfile.ZipFile")
    @patch("lava_dispatcher.actions.deploy.avh.plistlib.dump")
    @patch(
        "lava_dispatcher.actions.deploy.avh.arm_api.ArmApi.v1_get_projects",
        return_value=[
            Project("d59db33d-27bd-4b22-878d-49e4758a648e", name="Default Project"),
        ],
    )
    @patch(
        "lava_dispatcher.actions.deploy.avh.arm_api.ArmApi.v1_get_models",
        return_value=[
            Model("iot", "rpi4b", "rpi4b", "rpi4b"),
        ],
    )
    @patch(
        "lava_dispatcher.actions.deploy.avh.arm_api.ArmApi.v1_auth_login",
        return_value=Token("avhapitoken"),
    )
    def test_deploy(
        self,
        v1_auth_login,
        v1_get_models,
        v1_get_projects,
        plist_dump,
        zip_file,
        zf_write,
        *args,
    ):
        self.job.validate()

        action = self.job.pipeline.actions[0].pipeline.actions[0]
        action.run(None, None)

        v1_auth_login.assert_called_once_with({"api_token": "avh_api_token"})
        v1_get_models.assert_called_once_with()
        v1_get_projects.assert_called_once_with()

        # ANY: Info.plist file path with random string inside.
        plist_dump.assert_called_with(
            {
                "Type": "iot",
                "UniqueIdentifier": f"lava-avh-rpi4b-1.1-{self.job.job_id}-rrrrr",
                "DeviceIdentifier": "rpi4b",
                "Version": "1.1",
                "Build": self.job.job_id,
            },
            ANY,
        )

        # ANY: image path with random string inside.
        # Zip file compression method 'ZIP_DEFLATED = 8'
        zip_file.assert_called_once_with(ANY, mode="w", compression=8)
        zf_write.has_calls(
            [
                call(ANY, arcname="Info.plist"),
                call(ANY, arcname="kernel"),
                call(ANY, arcname="devicetree"),
                call(ANY, arcname="nand"),
            ],
            any_order=True,
        )

    # Test boot run.
    @patch("lava_dispatcher.actions.boot.avh.ShellSession")
    @patch("lava_dispatcher.actions.boot.avh.ShellCommand")
    @patch("lava_dispatcher.actions.boot.avh.DockerRun.prepare")
    @patch(
        "lava_dispatcher.actions.boot.avh.arm_api.ArmApi.v1_get_instance_console",
        return_value=InstanceConsoleEndpoint(
            url="wss://app.avh.corellium.com/console/q2Q4vZ0nJv"
        ),
    )
    @patch(
        "lava_dispatcher.actions.boot.avh.arm_api.ArmApi.v1_get_instance_state",
        side_effect=[InstanceState("creating"), InstanceState("on")],
    )
    @patch(
        "lava_dispatcher.actions.boot.avh.arm_api.ArmApi.v1_create_instance",
        return_value=InstanceReturn(
            "7f4f241c-821f-4219-905f-c3b50b0db5dd", InstanceState("creating")
        ),
    )
    @patch(
        "lava_dispatcher.actions.boot.avh.arm_api.ArmApi.v1_create_image",
        return_value=Image("active", id="18af26fe-8a5a-479a-80ec-013c54176d6f"),
    )
    @patch("lava_dispatcher.actions.boot.avh.open")
    @patch(
        "lava_dispatcher.actions.boot.avh.arm_api.ArmApi.v1_auth_login",
        return_value=Token("avhapitoken"),
    )
    @patch(
        "lava_dispatcher.actions.boot.avh.CallAvhAction.get_namespace_data",
        return_value={
            "model": "rpi4b",
            "api_endpoint": "https://app.avh.corellium.com/api",
            "project_name": "Default Project",
            "api_token": "avh_api_token",
            "project_id": "d59db33d-27bd-4b22-878d-49e4758a648e",
            "image_name": "lava-avh-rpi4b-1.1-4-6A2cA",
            "image_path": "/var/lib/lava/dispatcher/tmp/4/deploy-avh-6h9bjj3g/lava-avh-rpi4b-1.1-4-59c0d.zip",
            "image_version": "1.1",
            "image_build": "4",
            "image_id": "18af26fe-8a5a-479a-80ec-013c54176d6f",
        },
    )
    def test_boot(
        self,
        get_namespace_data,
        v1_auth_login,
        image_open,
        v1_create_image,
        v1_create_instance,
        v1_get_instance_state,
        v1_get_instance_console,
        *args,
    ):
        self.job.validate()

        action = self.job.pipeline.actions[1].pipeline.actions[0]
        action.run(None, None)

        get_namespace_data.assert_called_once_with(
            action="deploy-avh", label="deploy-avh", key="avh"
        )

        v1_auth_login.assert_called_once_with({"api_token": "avh_api_token"})

        image_open.assert_called_once_with(
            "/var/lib/lava/dispatcher/tmp/4/deploy-avh-6h9bjj3g/lava-avh-rpi4b-1.1-4-59c0d.zip",
            "rb",
        )
        v1_create_image.assert_called_once_with(
            type="fwpackage",
            encoding="plain",
            name="lava-avh-rpi4b-1.1-4-6A2cA",
            project="d59db33d-27bd-4b22-878d-49e4758a648e",
            file=ANY,
        )

        v1_create_instance.assert_called_once_with(
            {
                "name": "lava-avh-rpi4b-1.1-4-6A2cA",
                "project": "d59db33d-27bd-4b22-878d-49e4758a648e",
                "flavor": "rpi4b",
                "fwpackage": "18af26fe-8a5a-479a-80ec-013c54176d6f",
                "os": "1.1",
                "osbuild": "4",
                "boot_options": {
                    "boot_args": "earlycon=uart8250,mmio32,0xfe215040 console=ttyS0,115200n8 rw rootwait root=/dev/mmcblk0p2 coherent_pool=1M 8250.nr_uarts=1 cma=64M log_buf_len=1M",
                    "restore_boot_args": "earlycon=uart8250,mmio32,0xfe215040 console=ttyS0,115200n8 console=tty0 rw rootwait root=/dev/mmcblk0p2 coherent_pool=1M 8250.nr_uarts=1 cma=64M log_buf_len=1M init=/usr/lib/raspi-config/init_resize.sh",
                },
            }
        )

        v1_get_instance_state.assert_has_calls(
            [
                call("7f4f241c-821f-4219-905f-c3b50b0db5dd"),
                call("7f4f241c-821f-4219-905f-c3b50b0db5dd"),
            ]
        )

        v1_get_instance_console.assert_called_once_with(
            "7f4f241c-821f-4219-905f-c3b50b0db5dd"
        )
