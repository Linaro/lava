# Copyright (C) 2016 Linaro Limited
#
# Author: Dean Arnold <dean.arnold@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.
from __future__ import annotations

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import (
    ApplyOverlayTftp,
    ExtractModules,
    ExtractNfsRootfs,
    OverlayAction,
)
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment


class NfsAction(Action):
    name = "nfs-deploy"
    description = "deploy nfsrootfs"
    summary = "NFS deployment"

    def validate(self):
        super().validate()
        if not self.valid:
            return
        if "nfsrootfs" in self.parameters and "persistent_nfs" in self.parameters:
            self.errors = "Only one of nfsrootfs or persistent_nfs can be specified"

    def populate(self, parameters):
        download_dir = self.mkdtemp()
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if "nfsrootfs" in parameters:
            self.pipeline.add_action(
                DownloaderAction(
                    self.job,
                    "nfsrootfs",
                    path=download_dir,
                    params=parameters["nfsrootfs"],
                )
            )
        if "modules" in parameters:
            self.pipeline.add_action(
                DownloaderAction(
                    self.job, "modules", path=download_dir, params=parameters["modules"]
                )
            )
        # NfsAction is a deployment, so once the nfsrootfs has been deployed, just do the overlay
        self.pipeline.add_action(ExtractNfsRootfs(self.job))
        self.pipeline.add_action(OverlayAction(self.job))
        self.pipeline.add_action(ExtractModules(self.job))
        self.pipeline.add_action(ApplyOverlayTftp(self.job))
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment(self.job))
