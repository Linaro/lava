# Copyright (C) 2024 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.deploy.download import DownloadAction, DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.utils.strings import substitute

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class USBGMSAction(DownloadAction):
    name = "usbg-ms"
    description = "USB Gadget Mass storage"
    summary = "USBG MS"
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError

    def __init__(self, job: Job):
        super().__init__(job)
        method = self.job.device["actions"]["deploy"]["methods"]["usbg-ms"]
        self.disable = method["disable"]
        self.enable = method["enable"]

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
        super().validate()
        if not self.valid:
            return
        if "image" not in self.parameters:
            raise JobError("Missing 'image'")

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        image = self.get_namespace_data(
            action="download-action", label="image", key="file"
        )
        self.run_cmd(self.disable, allow_fail=True)
        self.logger.info("Creating USB gadget MS for %s", image)

        # Substitute in the command line
        substitutions = {"{IMAGE}": image}
        cmds = substitute(self.enable, substitutions)
        self.run_cmd(cmds)
        return connection

    def cleanup(self, connection):
        self.logger.info("Remove USB gadget MS")
        self.run_cmd(self.disable, allow_fail=True)
        super().cleanup(connection)
