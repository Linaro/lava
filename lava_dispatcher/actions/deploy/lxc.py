# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from lava_common.constants import (
    LXC_DEFAULT_PACKAGES,
    LXC_PATH,
    LXC_TEMPLATE_WITH_MIRROR,
)
from lava_common.exceptions import InfrastructureError, LAVABug
from lava_common.utils import debian_package_version
from lava_dispatcher.action import Action, JobError, Pipeline
from lava_dispatcher.actions.boot.lxc import LxcStartAction, LxcStopAction
from lava_dispatcher.actions.deploy.apply_overlay import ApplyLxcOverlay
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.protocols.lxc import LxcProtocol
from lava_dispatcher.utils.filesystem import lxc_path
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.udev import allow_fs_label
from lava_dispatcher_host.action import DeviceContainerMappingMixin


class Lxc(Deployment):
    """
    Strategy class for a lxc deployment.
    Downloads the relevant parts, copies to the locations using lxc.
    """

    name = "lxc"

    @classmethod
    def action(cls):
        return LxcAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "lxc":
            return False, '"to" parameter is not "lxc"'
        if "lxc" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"lxc" was not in the device configuration deploy methods'


class LxcAction(Action):
    name = "lxc-deploy"
    description = "download files and deploy using lxc"
    summary = "lxc deployment"

    def __init__(self):
        super().__init__()
        self.lxc_data = {}

    def validate(self):
        super().validate()
        lxc_version = debian_package_version(pkg="lxc")
        if lxc_version != "":
            self.logger.info("lxc, installed at version: %s", lxc_version)
        else:
            self.logger.info(
                "lava-lxc-mocker, installed at version: %s",
                debian_package_version(pkg="lava-lxc-mocker"),
            )
        protocols = [protocol.name for protocol in self.job.protocols]
        if LxcProtocol.name not in protocols:
            self.logger.debug(
                "Missing protocol '%s' in %s", LxcProtocol.name, protocols
            )
            self.errors = "Missing protocol '%s'" % LxcProtocol.name
        which("lxc-create")

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(LxcCreateAction())
        self.pipeline.add_action(LxcCreateUdevRuleAction())
        if "packages" in parameters:
            self.pipeline.add_action(LxcStartAction())
            self.pipeline.add_action(LxcAptUpdateAction())
            self.pipeline.add_action(LxcAptInstallAction())
            self.pipeline.add_action(LxcStopAction())
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment())
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())
            self.pipeline.add_action(ApplyLxcOverlay())


class LxcCreateAction(Action):
    """
    Creates Lxc container.
    """

    name = "lxc-create-action"
    description = "create lxc action"
    summary = "create lxc"

    def __init__(self):
        super().__init__()
        self.retries = 10
        self.sleep = 10
        self.lxc_data = {}

    def _set_lxc_data(self):
        protocols = [
            protocol
            for protocol in self.job.protocols
            if protocol.name == LxcProtocol.name
        ]
        if protocols:
            protocol = protocols[0]
            self.set_namespace_data(
                action=self.name, label="lxc", key="name", value=protocol.lxc_name
            )
            self.lxc_data["lxc_name"] = protocol.lxc_name
            self.lxc_data["lxc_distribution"] = protocol.lxc_dist
            self.lxc_data["lxc_release"] = protocol.lxc_release
            self.lxc_data["lxc_arch"] = protocol.lxc_arch
            self.lxc_data["lxc_template"] = protocol.lxc_template
            self.lxc_data["lxc_mirror"] = protocol.lxc_mirror
            self.lxc_data["lxc_security_mirror"] = protocol.lxc_security_mirror
            self.lxc_data["verbose"] = protocol.verbose
            self.lxc_data["lxc_persist"] = protocol.persistence
            self.lxc_data["custom_lxc_path"] = protocol.custom_lxc_path

    def validate(self):
        super().validate()
        # set lxc_data
        self._set_lxc_data()

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        verbose = "" if self.lxc_data["verbose"] else "-q"
        lxc_default_path = lxc_path(self.job.parameters["dispatcher"])
        if self.lxc_data["custom_lxc_path"]:
            lxc_create = ["lxc-create", "-P", lxc_default_path]
        else:
            lxc_create = ["lxc-create"]
        if self.lxc_data["lxc_template"] in LXC_TEMPLATE_WITH_MIRROR:
            lxc_cmd = lxc_create + [
                verbose,
                "-t",
                self.lxc_data["lxc_template"],
                "-n",
                self.lxc_data["lxc_name"],
                "--",
                "--release",
                self.lxc_data["lxc_release"],
            ]
            if self.lxc_data["lxc_mirror"]:
                lxc_cmd += ["--mirror", self.lxc_data["lxc_mirror"]]
            if self.lxc_data["lxc_security_mirror"]:
                lxc_cmd += ["--security-mirror", self.lxc_data["lxc_security_mirror"]]
            # FIXME: Should be removed when LAVA's supported distro is bumped
            #        to Debian Stretch or any distro that supports systemd
            lxc_cmd += ["--packages", LXC_DEFAULT_PACKAGES]
        else:
            lxc_cmd = lxc_create + [
                verbose,
                "-t",
                self.lxc_data["lxc_template"],
                "-n",
                self.lxc_data["lxc_name"],
                "--",
                "--dist",
                self.lxc_data["lxc_distribution"],
                "--release",
                self.lxc_data["lxc_release"],
            ]
        if self.lxc_data["lxc_arch"]:
            lxc_cmd += ["--arch", self.lxc_data["lxc_arch"]]

        # Check if the container already exists. If this is a persistent that's
        # ok, otherwise, raise an error.
        if not self.run_cmd(
            ["lxc-info", "-n", self.lxc_data["lxc_name"]], allow_fail=True
        ):
            if not self.lxc_data["lxc_persist"]:
                raise InfrastructureError(
                    "lxc container %r already exists" % self.lxc_data["lxc_name"]
                )
            self.logger.debug("Persistent container exists")
        else:
            # The container does not exists, just create it
            self.run_cmd(lxc_cmd, error_msg="Unable to create lxc container")
            self.logger.debug("Container created successfully")
        self.results = {"status": self.lxc_data["lxc_name"]}

        # Create symlink in default container path ie., /var/lib/lxc defined by
        # LXC_PATH so that we need not add '-P' option to every lxc-* command.
        dst = os.path.join(LXC_PATH, self.lxc_data["lxc_name"])
        if self.lxc_data["custom_lxc_path"] and not os.path.exists(dst):
            os.symlink(
                os.path.join(lxc_default_path, self.lxc_data["lxc_name"]),
                os.path.join(LXC_PATH, self.lxc_data["lxc_name"]),
            )
        return connection


class LxcCreateUdevRuleAction(Action, DeviceContainerMappingMixin):
    """
    Creates Lxc related udev rules for this container.
    """

    name = "lxc-create-udev-rule-action"
    description = "create lxc udev rule action"
    summary = "create lxc udev rule"

    def __init__(self):
        super().__init__()
        self.retries = 10
        self.sleep = 10

    def validate(self):
        super().validate()
        which("udevadm")
        if "device_info" in self.job.device and not isinstance(
            self.job.device.get("device_info"), list
        ):
            self.errors = "device_info unset"
        # If we are allowed to use a filesystem label, we don't require a board_id
        # By default, we do require a board_id (serial)
        requires_board_id = not allow_fs_label(self.job.device)
        try:
            if "device_info" in self.job.device:
                for usb_device in self.job.device["device_info"]:
                    if (
                        usb_device.get("board_id", "") in ["", "0000000000"]
                        and requires_board_id
                    ):
                        self.errors = "[LXC_CREATE] board_id unset"
                    if usb_device.get("usb_vendor_id", "") == "0000":
                        self.errors = "[LXC_CREATE] usb_vendor_id unset"
                    if usb_device.get("usb_product_id", "") == "0000":
                        self.errors = "[LXC_CREATE] usb_product_id unset"
        except TypeError:
            self.errors = "Invalid parameters for %s" % self.name

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        # this may be the device namespace - the lxc namespace may not be
        # accessible
        lxc_name = None
        protocols = [
            protocol
            for protocol in self.job.protocols
            if protocol.name == LxcProtocol.name
        ]
        if protocols:
            lxc_name = protocols[0].lxc_name
        if not lxc_name:
            self.logger.debug("No LXC device requested")
            return connection

        # If there is no device_info then this action should be idempotent.
        if "device_info" not in self.job.device:
            return connection

        self.add_device_container_mappings(lxc_name, "lxc")

        return connection


class LxcAptUpdateAction(Action):
    """
    apt-get update the lxc container.
    """

    name = "lxc-apt-update"
    description = "lxc apt update action"
    summary = "lxc apt update"

    def __init__(self):
        super().__init__()
        self.retries = 10
        self.sleep = 10

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        lxc_name = self.get_namespace_data(
            action="lxc-create-action", label="lxc", key="name"
        )
        cmd = ["lxc-attach", "-n", lxc_name, "--", "apt-get", "-y", "-q", "update"]
        if not self.run_command(cmd, allow_silent=True):
            raise JobError("Unable to apt-get update in lxc container")
        return connection


class LxcAptInstallAction(Action):
    """
    apt-get install packages to the lxc container.
    """

    name = "lxc-apt-install"
    description = "lxc apt install packages action"
    summary = "lxc apt install"

    def __init__(self):
        super().__init__()
        self.retries = 10
        self.sleep = 10

    def validate(self):
        super().validate()
        if "packages" not in self.parameters:
            raise LAVABug("%s package list unavailable" % self.name)

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        lxc_name = self.get_namespace_data(
            action="lxc-create-action", label="lxc", key="name"
        )
        packages = self.parameters["packages"]
        cmd = [
            "lxc-attach",
            "-v",
            "DEBIAN_FRONTEND=noninteractive",
            "-n",
            lxc_name,
            "--",
            "apt-get",
            "-y",
            "-q",
            "install",
        ] + packages
        if not self.run_command(cmd):
            raise JobError("Unable to install using apt-get in lxc container")
        return connection
