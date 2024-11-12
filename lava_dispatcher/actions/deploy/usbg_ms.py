# Copyright (C) 2024 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.exceptions import ConfigurationError, InfrastructureError, JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloadAction, DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.utils.strings import substitute

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class USBGMS(Deployment):
    """
    Strategy class for a usbg-ms deployment.
    """

    name = "usbg-ms"

    @classmethod
    def action(cls, job: Job) -> Action:
        return USBGMSAction(job)

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["to"] != "usbg-ms":
            return False, '"to" parameter is not "usbg-ms"'
        if "usbg-ms" not in device["actions"]["deploy"]["methods"]:
            return False, "'usbg-ms' not in the device configuration deploy methods"
        keys = set(device["actions"]["deploy"]["methods"]["usbg-ms"].keys())
        if keys != {"disable", "enable"}:
            raise ConfigurationError(
                "usbg-ms 'disable' and 'enable' commands missing: %s", keys
            )
        return True, "accepted"


class USBGMSAction(DownloadAction):
    name = "usbg-ms"
    description = "USB Gadget Mass storage"
    summary = "USBG MS"
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        path = self.mkdtemp()

        if self.test_needs_overlay(parameters):
            # idempotent, includes testdef
            self.pipeline.add_action(OverlayAction(self.job))

        self.pipeline.add_action(
            DownloaderAction(self.job, "image", path, params=parameters["image"])
        )
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment(self.job))

    def validate(self):
        self.disable = method["disable"]
        self.enable = method["enable"]
        super().validate()
        if not self.valid:
            return
        if "image" not in self.parameters:
            raise JobError("Missing 'image'")
        method = self.job.device["actions"]["deploy"]["methods"]["usbg-ms"]

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        image = self.get_namespace_data(
            action="download-action", label="image", key="file"
        )
        self.logger.info("Creating USB gadget MS for %s", image)

        # Substitute in the command line
        substitutions = {"{IMAGE}": image}
        cmds = substitute(self.enable, substitutions)
        self.logger.debug("calling %s", cmds)
        self.run_cmd(cmds)
        return connection

    def cleanup(self, connection):
        self.logger.info("Remove USB gadget MS")
        self.run_cmd(self.disable, allow_fail=True)
        super().cleanup(connection)
