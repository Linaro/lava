# Copyright (C) 2017 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import plistlib
import random
import shutil
import string
import zipfile
from pathlib import Path

import avh_api as AvhApi
from avh_api.api import arm_api
from avh_api.exceptions import ForbiddenException

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import ApplyOverlayImage
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment, RetryAction
from lava_dispatcher.utils.network import retry


class Avh(Deployment):
    name = "avh"

    @classmethod
    def action(cls):
        return AvhRetryAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "avh" not in device["actions"]["deploy"]["methods"]:
            return False, "'avh' not in the device configuration deploy methods"
        if parameters["to"] != "avh":
            return False, "'to' parameter is not 'avh'"
        return True, "accepted"


class AvhRetryAction(RetryAction):
    name = "deploy-avh-retry"
    description = "deploy avh image with retry"
    summary = "deploy avh image"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(AvhDeploy())


class AvhDeploy(Action):
    name = "deploy-avh"
    description = "create and upload avh firmware zip package"
    summary = "create and upload avh firmware zip package"

    def __init__(self):
        super().__init__()
        self.avh = {}
        self.path = None
        self.required_images = [
            "kernel",
            "dtb",
            "rootfs",
        ]
        self.api_config = None

    def validate(self):
        super().validate()

        self.avh = self.job.device["actions"]["deploy"]["methods"]["avh"]["options"]
        job_options = self.parameters.get("options")
        if job_options:
            if not isinstance(job_options, dict):
                raise JobError("'deploy.options' should be a dictionary")
            self.avh.update(job_options)
        if self.avh.get("model") is None:
            raise JobError(
                "avh 'options.model' not provided in either device dictionary or job definition"
            )

        secrets = self.job.parameters.get("secrets")
        if "avh_api_token" not in secrets:
            raise JobError("'secrets.avh_api_token' key is required for AVH deploy")
        self.avh["api_token"] = secrets["avh_api_token"]
        if not isinstance(self.avh["api_token"], str):
            raise JobError("'secrets.avh_api_token' should be a string")

        images = self.parameters.get("images")
        if not images:
            raise JobError("No 'images' specified for AVH deploy")
        if not isinstance(images, dict):
            raise JobError("'deploy.images' should be a dictionary")
        for image in self.required_images:
            if image not in images.keys():
                raise JobError(f"No '{image}' image specified for AVH deploy")

        if (
            self.test_needs_overlay(self.parameters)
            and images["rootfs"].get("root_partition") is None
        ):
            raise JobError("Unable to apply overlay without 'root_partition'")

    def populate(self, parameters):
        self.path = self.mkdtemp()
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())

        images = parameters.get("images")
        uniquify = parameters.get("uniquify", True)
        for image in images.keys():
            self.pipeline.add_action(
                DownloaderAction(image, self.path, images[image], uniquify=uniquify)
            )
            if image == "rootfs" and self.test_needs_overlay(parameters):
                self.pipeline.add_action(
                    ApplyOverlayImage(image_key=image, use_root_partition=True)
                )

    @retry(exception=AvhApi.ApiException, retries=3, delay=1)
    def v1_auth_login(self, api_instance):
        return api_instance.v1_auth_login({"api_token": self.avh["api_token"]})

    @retry(exception=AvhApi.ApiException, retries=3, delay=1)
    def v1_get_models(self, api_instance):
        return api_instance.v1_get_models()

    @retry(exception=AvhApi.ApiException, retries=3, delay=1)
    def v1_get_projects(self, api_instance):
        return api_instance.v1_get_projects()

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        self.api_config = AvhApi.Configuration(self.avh["api_endpoint"])
        with AvhApi.ApiClient(self.api_config) as api_client:
            api_instance = arm_api.ArmApi(api_client)
            try:
                token_response = self.v1_auth_login(api_instance)
            except ForbiddenException as exc:
                raise JobError(str(exc))
            self.api_config.access_token = token_response.token
            self.logger.info("AVH API session created")

            # Check if the specified model is supported
            models = self.v1_get_models(api_instance)
            model_list = [model.flavor for model in models]
            if self.avh["model"] not in model_list:
                raise JobError(
                    f"{self.avh['model']} is not a supported model! Supported AVH models are: {', '.join(model_list)}"
                )

            # Find project ID
            projects = self.v1_get_projects(api_instance)
            for project in projects:
                if project.name == self.avh["project_name"]:
                    self.avh["project_id"] = project.id
            if self.avh.get("project_id") is None:
                raise JobError(f"AVH project '{self.avh['project_name']}' NOT found!")
            self.logger.info(f"AVH project ID: {self.avh['project_id']}")

        # Create Info.plist
        fw_version = self.level
        fw_build = self.job.job_id
        rand = "".join(random.choice(string.hexdigits) for c in range(5))
        fw_name = f"lava-avh-{self.avh['model']}-{fw_version}-{fw_build}-{rand}"
        pl = dict(
            Type="iot",
            UniqueIdentifier=fw_name,
            DeviceIdentifier=self.avh["model"],
            Version=fw_version,
            Build=fw_build,
        )
        plist_file = Path(self.path) / "Info.plist"
        self.logger.info(f"Generating {plist_file}")
        with plist_file.open("wb") as bf:
            plistlib.dump(pl, bf)

        self.avh["image_name"] = fw_name
        self.avh["image_version"] = fw_version
        self.avh["image_build"] = fw_build

        downloaded_images = {}
        for image in self.parameters["images"].keys():
            filename = self.get_namespace_data(
                action="download-action", label=image, key="file"
            )
            downloaded_images[image] = filename

        # Create firmware zip package
        fw_path = os.path.join(self.path, f"{fw_name}.zip")
        self.logger.info(f"Creating AVH firmware zip package {fw_path}")
        with zipfile.ZipFile(fw_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            self.logger.info(f"Adding: Info.plist")
            zf.write(plist_file, arcname="Info.plist")
            self.logger.info(f"Adding: kernel")
            zf.write(downloaded_images["kernel"], arcname="kernel")
            self.logger.info(f"Adding: devicetree")
            zf.write(downloaded_images["dtb"], arcname="devicetree")
            self.logger.info(f"Adding: nand")
            zf.write(downloaded_images["rootfs"], arcname="nand")

        self.avh["image_path"] = fw_path
        self.set_namespace_data(
            action=self.name, label=self.name, key="avh", value=self.avh
        )
        self.results = {"success": fw_path}

        return connection

    def cleanup(self, connection):
        super().cleanup(connection)

        if os.path.exists(self.path):
            self.logger.debug(f"Cleaning up AVH deploy directory {self.path}")
            shutil.rmtree(self.path)
