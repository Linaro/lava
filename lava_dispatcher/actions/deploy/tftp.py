# Copyright (C) 2014,2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.
from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING

from lava_common.constants import TFTP_SIZE_LIMIT
from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import PrepareOverlayTftp
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.lxc import LxcCreateUdevRuleAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.utils import filesystem
from lava_dispatcher.utils.shell import which

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class TftpAction(Action):
    name = "tftp-deploy"
    description = "download files and deploy using tftp"
    summary = "tftp deployment"

    def __init__(self, job: Job):
        super().__init__(job)
        self.tftp_dir = None

    def validate(self):
        super().validate()
        if "kernel" not in self.parameters:
            self.errors = "%s needs a kernel to deploy" % self.name
        if not self.valid:
            return
        if "nfsrootfs" in self.parameters and "persistent_nfs" in self.parameters:
            self.errors = "Only one of nfsrootfs or persistent_nfs can be specified"
        which("in.tftpd")

        # Check that the tmp directory is in the tftpd_dir or in /tmp for the
        # unit tests
        tftpd_directory = os.path.realpath(filesystem.tftpd_dir())
        tftp_dir = os.path.realpath(self.tftp_dir)
        tmp_dir = tempfile.gettempdir()
        if not tftp_dir.startswith(tftpd_directory) and not tftp_dir.startswith(
            tmp_dir
        ):
            self.errors = "tftpd directory is not configured correctly, see /etc/default/tftpd-hpa"

    def populate(self, parameters):
        self.tftp_dir = self.mkdtemp(override=filesystem.tftpd_dir())
        self.set_namespace_data(
            action=self.name,
            label="tftp",
            key="tftp_dir",
            value=self.tftp_dir,
            parameters=parameters,
        )

        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction(self.job))

        for key in [
            "ramdisk",
            "kernel",
            "dtb",
            "nfsrootfs",
            "modules",
            "preseed",
            "tee",
            "dtbo",
        ]:
            if key in parameters:
                if key == "dtbo":
                    for index, parameter in enumerate(parameters[key]):
                        self.pipeline.add_action(
                            DownloaderAction(
                                self.job,
                                f"{key}{index}",
                                path=self.tftp_dir,
                                params=parameter,
                            )
                        )
                else:
                    self.pipeline.add_action(
                        DownloaderAction(
                            self.job, key, path=self.tftp_dir, params=parameters[key]
                        )
                    )
                    if key == "ramdisk":
                        self.set_namespace_data(
                            action=self.name,
                            label="tftp",
                            key="ramdisk",
                            value=True,
                            parameters=parameters,
                        )

        # TftpAction is a deployment, so once the files are in place, just do the overlay
        self.pipeline.add_action(PrepareOverlayTftp(self.job))
        self.pipeline.add_action(LxcCreateUdevRuleAction(self.job))
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment(self.job))

    def run(self, connection, max_end_time):
        # Extract the 3 last path elements. See action.mkdtemp()
        suffix = os.path.join(*self.tftp_dir.split("/")[-2:])
        self.set_namespace_data(
            action=self.name, label="tftp", key="suffix", value=suffix
        )

        super().run(connection, max_end_time)
        tftp_size_limit = self.job.parameters["dispatcher"].get(
            "tftp_size_limit", TFTP_SIZE_LIMIT
        )
        self.logger.debug("Checking files for TFTP limit of %s bytes.", tftp_size_limit)
        for action, key in [
            ("compress-ramdisk", "ramdisk"),
            ("download-action", "kernel"),
            ("download-action", "dtb"),
            ("download-action", "tee"),
        ]:
            if key in self.parameters:
                filename = self.get_namespace_data(action=action, label="file", key=key)
                filename = os.path.join(filesystem.tftpd_dir(), filename)
                fsize = os.stat(filename).st_size
                if fsize >= tftp_size_limit:
                    raise JobError(
                        "Unable to send '%s' over tftp: file too large (%d > %d)"
                        % (os.path.basename(filename), fsize, tftp_size_limit)
                    )
        return connection
