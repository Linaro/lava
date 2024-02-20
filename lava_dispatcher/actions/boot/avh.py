# Copyright (C) 2017 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import time

import avh_api as AvhApi
from avh_api.api import arm_api
from avh_api.exceptions import NotFoundException
from avh_api.model.instance_state import InstanceState

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, BootHasMixin
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.shell import ExpectShellSession, ShellCommand, ShellSession
from lava_dispatcher.utils.docker import DockerRun
from lava_dispatcher.utils.network import retry


class BootAvh(Boot):
    @classmethod
    def action(cls):
        return BootAvhAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "avh" not in device["actions"]["boot"]["methods"]:
            return False, "'avh' not in the device configuration boot methods"
        if parameters["method"] != "avh":
            return False, "'method' is not 'avh'"
        return True, "accepted"


class BootAvhAction(BootHasMixin, RetryAction):
    name = "boot-avh"
    description = "boot avh device"
    summary = "boot avh device"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(CallAvhAction())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                self.pipeline.add_action(ExportDeviceEnvironment())


class CallAvhAction(Action):
    name = "call-avh"
    description = "call avh api"
    summary = "call avh api"

    def __init__(self):
        super().__init__()
        self.docker_cleanup_required = False
        self.websocat_docker_image = "ghcr.io/vi/websocat:1.12.0"
        self.api_config = None
        self.bootargs = None
        self.avh = {}
        self.image_id = None
        self.instance_id = None
        self.instance_name = None

    def validate(self):
        super().validate()
        self.bootargs = self.parameters.get("bootargs")
        if self.bootargs and not isinstance(self.bootargs, dict):
            raise JobError("'boot.bootargs' should be a dictionary")

    @retry(exception=AvhApi.ApiException, retries=3, delay=1)
    def v1_auth_login(self, api_instance):
        return api_instance.v1_auth_login({"api_token": self.avh["api_token"]})

    @retry(exception=AvhApi.ApiException, retries=6, delay=5)
    def v1_create_instance(self, api_instance, instance_options):
        return api_instance.v1_create_instance(instance_options)

    @retry(exception=AvhApi.ApiException, retries=3, delay=1)
    def v1_get_instance_state(self, api_instance):
        return api_instance.v1_get_instance_state(self.instance_id)

    @retry(exception=AvhApi.ApiException, retries=3, delay=1)
    def v1_get_instance(self, api_instance):
        return api_instance.v1_get_instance(self.instance_id)

    @retry(exception=AvhApi.ApiException, retries=6, delay=5)
    def v1_get_instance_console(self, api_instance):
        return api_instance.v1_get_instance_console(self.instance_id)

    @retry(exception=AvhApi.ApiException, retries=6, delay=5)
    def v1_create_image(self, api_instance, **kwargs):
        return api_instance.v1_create_image(**kwargs)

    @retry(
        exception=AvhApi.ApiException, expected=NotFoundException, retries=6, delay=5
    )
    def v1_delete_image(self, api_instance):
        return api_instance.v1_delete_image(self.image_id)

    @retry(
        exception=AvhApi.ApiException, expected=NotFoundException, retries=6, delay=5
    )
    def v1_delete_instance(self, api_instance):
        return api_instance.v1_delete_instance(self.instance_id)

    def run(self, connection, max_end_time):
        self.avh = self.get_namespace_data(
            action="deploy-avh", label="deploy-avh", key="avh"
        )
        if self.avh is None:
            raise JobError(
                "AVH image attributes not found! Is 'deploy.avh' action defined before the 'boot.avh' action?"
            )
        self.instance_name = self.avh["image_name"]

        self.api_config = AvhApi.Configuration(self.avh["api_endpoint"])
        with AvhApi.ApiClient(self.api_config) as api_client:
            api_instance = arm_api.ArmApi(api_client)
            # Log in
            token_response = self.v1_auth_login(api_instance)
            self.api_config.access_token = token_response.token
            self.logger.info("AVH API session created")

            # Upload firmware package
            image_path = self.avh["image_path"]
            self.logger.info(f"Uploading: {image_path}")
            with open(image_path, "rb") as f:
                uploaded_image = self.v1_create_image(
                    api_instance,
                    type="fwpackage",
                    encoding="plain",
                    name=self.avh["image_name"],
                    project=self.avh["project_id"],
                    file=f,
                )
                self.image_id = uploaded_image.id
            self.logger.info(f"AVH image ID: {self.image_id}")

            # Assemble instance create options
            instance_options = {
                "name": self.instance_name,
                "project": self.avh["project_id"],
                "flavor": self.avh["model"],
                "fwpackage": self.image_id,
                "os": self.avh["image_version"],
                "osbuild": self.avh["image_build"],
            }
            if self.bootargs:
                boot_options = {}
                if self.bootargs.get("normal"):
                    boot_options["boot_args"] = self.bootargs.get("normal")
                if self.bootargs.get("restore"):
                    boot_options["restore_boot_args"] = self.bootargs.get("restore")
                instance_options["boot_options"] = boot_options
            # Create instance
            self.logger.info(f"Creating AVH instance with options: {instance_options}")
            instance_return = self.v1_create_instance(api_instance, instance_options)
            self.instance_id = instance_return.id
            self.logger.info(f"AVH instance ID: {self.instance_id}")
            # Wait for device ready
            instance_state = self.v1_get_instance_state(api_instance)
            while instance_state != InstanceState("on"):
                time.sleep(3)
                instance_state = self.v1_get_instance_state(api_instance)
                self.logger.info(f"Instance state: {instance_state}")
                if instance_state == InstanceState("error"):
                    instance = self.v1_get_instance(api_instance)
                    self.logger.error(f"Instance error: {instance.error}")
                    raise JobError("Instance entered error state")

            # Get device console websocket url
            console_ws = self.v1_get_instance_console(api_instance)

        # Connect to device
        if "docker" in self.parameters:
            docker_params = self.parameters["docker"]
        else:
            docker_params = {"image": self.websocat_docker_image}
        self.docker = DockerRun.from_parameters(docker_params, self.job)
        if not docker_params.get("container_name"):
            self.docker.name(
                f"lava-docker-avh-websocat-{self.job.job_id}-{self.level}",
                random_suffix=True,
            )
        self.docker.init(False)
        self.docker.tty()
        self.docker.interactive()
        docker_cmdline_args = ["-b", console_ws.url]
        console_cmd = " ".join(self.docker.cmdline(*docker_cmdline_args))
        self.docker.prepare(action=self)
        self.docker_cleanup_required = True
        self.logger.info(f"Connecting to instance {self.instance_id} console ...")
        shell = ShellCommand(console_cmd, self.timeout, logger=self.logger)
        shell_connection = ShellSession(self.job, shell)
        shell_connection = super().run(shell_connection, max_end_time)

        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=shell_connection
        )
        return shell_connection

    def cleanup(self, connection):
        super().cleanup(connection)

        if self.image_id:
            self.logger.info(f"Deleting AVH image {self.image_id}")
            with AvhApi.ApiClient(self.api_config) as api_client:
                api_instance = arm_api.ArmApi(api_client)
                self.v1_delete_image(api_instance)

        if self.instance_id:
            self.logger.info(f"Deleting AVH instance {self.instance_id}")
            with AvhApi.ApiClient(self.api_config) as api_client:
                api_instance = arm_api.ArmApi(api_client)
                self.v1_delete_instance(api_instance)

        if self.docker_cleanup_required:
            self.logger.info(f"Stopping the websocat container {self.docker.__name__}")
            self.docker.destroy()
