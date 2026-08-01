# Copyright (C) 2026 Qualcomm Inc.
#
# Author: Milosz Wasilewski <milosz.wasilewski@oss.qualcomm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from lava_common.exceptions import ConfigurationError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.udev import WaitQDLDeviceAction

if TYPE_CHECKING:
    from lava_dispatcher.job import Job

# The version reported by "qdl --version" depends on how qdl was built:
#   "qdl version v2.7"          built from a git tag
#   "qdl version 2.7-1~bpo13+1" built from a Debian package, which reports the
#                               Debian package version, i.e.
#                               [epoch:]upstream_version[-debian_revision]
# Only the major and minor numbers of the upstream version are of interest,
# anything after them is ignored.
QDL_VERSION_PATTERN = re.compile(
    r"qdl version (?:\d+:)?v?(?P<major>\d+)\.(?P<minor>\d+)"
)


class BootQDLRetry(RetryAction):
    name = "boot-qdl-retry"
    description = "boot to EDL mode using any available method"
    summary = "boot to EDL mode"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ConnectDevice(self.job))
        self.pipeline.add_action(ResetDevice(self.job))
        self.pipeline.add_action(EnterQDL(self.job))
        self.pipeline.add_action(WaitQDLDeviceAction(self.job))
        self.pipeline.add_action(FlashQDLAction(self.job))


class EnterQDL(Action):
    name = "enter-qdl"
    description = "enter QDL mode"
    summary = "enter QDL mode"

    def validate(self):
        super().validate()
        parameters = self.job.device["actions"]["boot"]["methods"]["qdl"]["parameters"]
        if "enter-commands" not in parameters:
            self.errors_add('"enter-commands" is not defined')
        elif not isinstance(parameters["enter-commands"], list):
            self.errors_add('"enter-commands" should be a list')

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        parameters = self.job.device["actions"]["boot"]["methods"]["qdl"]["parameters"]
        for _, cmd in enumerate(parameters["enter-commands"]):
            # this should run on the dispatcher
            self.run_cmd(cmd)


class FlashQDLAction(Action):
    name = "flash-qdl"
    description = "use qdl to flash flat build to the board"
    summary = "use qdl to flash flat build to the board"

    def __init__(self, job: Job, params=None):
        super().__init__(job)
        self.base_command = []
        self.exec_list = []
        self.board_qdl_id = "00000000"
        self.board_id = "0000000000"
        self.usb_vendor_id = "0000"
        self.usb_product_id = "0000"
        self.qcomflash_path = None  # path inside tarball where .XML files are located
        self.params = params

    def validate(self):
        super().validate()
        # - boot:
        #     firehose_program: "prog_firehose_ddr.elf"
        #     rawprogram: "rawprogram*.xml"
        #     patch: "patch*.xml"
        #     storage: "emmc"
        #     timeout:
        #       minutes: 5
        #     method: qdl

        try:
            boot = self.job.device["actions"]["boot"]["methods"]["qdl"]
            qdl_command = boot["parameters"]["command"]
            qdl_binary = which(qdl_command)
            if not qdl_binary:
                self.logger.error("%r was not found in PATH", qdl_command)
                raise ConfigurationError(f"qdl not installed: {qdl_command} not found")
            # all paths are relative to the tarball
            qdl_flashing_prog_path = self.parameters["firehose_program"]
            qdl_rawprogram_path = self.parameters["rawprogram"]
            qdl_patch_path = self.parameters["patch"]
            qdl_storage = self.parameters.get("storage", None)
            qdl_debug = self.parameters.get("debug", False)
            self.qcomflash_path = self.parameters.get("path", ".")
            self.base_command = [qdl_binary]
            # execute qdl to detect version
            version_command = [qdl_binary, "--version"]
            qdl_output = self.parsed_command(version_command)
            match = QDL_VERSION_PATTERN.search(qdl_output)
            if not match:
                self.logger.error(
                    "Unable to parse the version reported by '%s --version': %r",
                    qdl_binary,
                    qdl_output.strip(),
                )
                raise ConfigurationError(
                    f"Unable to parse the version of qdl at {qdl_binary}"
                )
            version = (int(match.group("major")), int(match.group("minor")))
            self.logger.info("Detected qdl version %d.%d at %s", *version, qdl_binary)

            if version < (2, 0):
                # version lower than 2.0 is unsupported
                self.logger.error("qdl version 2.0 or higher is required")
                raise ConfigurationError(
                    "qdl version %d.%d is too low, 2.0 or higher is required" % version
                )

            if version >= (2, 7):
                # --skipblock=sha256 is available
                self.base_command.append("--skipblock=sha256")

            if qdl_debug:
                self.base_command.extend(["--debug"])
            if qdl_storage:
                self.base_command.extend(["--storage", qdl_storage])
            if self.job.device["board_qdl_id"] == "00000000":
                self.errors_add("[FLASH_QDL] board_qdl_id unset")
            self.usb_vendor_id = self.job.device["usb_vendor_id"]
            self.usb_product_id = self.job.device["usb_product_id"]
            self.board_qdl_id = self.job.device["board_qdl_id"]
            self.board_id = self.job.device["board_id"]
            self.base_command.extend(["--serial", self.board_qdl_id])
            self.base_command.extend(
                [qdl_flashing_prog_path, qdl_rawprogram_path, qdl_patch_path]
            )
        except AttributeError as exc:
            raise ConfigurationError(exc)
        except (KeyError, TypeError) as exc:
            self.errors_add(f"Invalid parameters for {self.name}: {exc}")
        self.exec_list.append(self.base_command)
        if not self.exec_list:
            self.errors_add("No QDL commands to execute")

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        qcomflash_dir = self.get_namespace_data(
            action="qdl-deploy", label="qdl-directory", key="directory"
        )

        # at this stage it's assumed that qcomflash tarball is decompressed
        for _, qdl_command in enumerate(self.exec_list):
            qdl_cmd = " ".join(qdl_command)
            flash_dir = os.path.join(qcomflash_dir.as_posix(), self.qcomflash_path)
            self.run_cmd(qdl_cmd.split(" "), cwd=flash_dir)

        return connection
