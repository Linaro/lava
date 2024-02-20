# Copyright (C) 2016 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from lava_common.constants import INSTALLER_IMAGE_MAX_SIZE
from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import ApplyOverlayGuest
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.utils import filesystem
from lava_dispatcher.utils.filesystem import copy_out_files, prepare_install_base
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.shell import which


class DeployIsoAction(Action):
    """
    Prepare an empty image, pull the specified kernel and initrd
    out of the iso using loopback and then start QEMU with the
    ISO as a cdrom and empty image as the destination.
    """

    name = "deploy-iso-installer"
    description = "setup deployment for emulated installer"
    summary = "pull kernel and initrd out of iso"

    def __init__(self):
        """
        Uses the tftp directory for easier cleanup and for parity
        with the non-QEMU Debian Installer support.
        """
        super().__init__()
        self.preseed_path = None

    def validate(self):
        super().validate()
        suffix = os.path.join(*self.preseed_path.split("/")[-2:])
        self.set_namespace_data(
            action=self.name, label="iso", key="suffix", value=suffix
        )
        which("in.tftpd")

    def populate(self, parameters):
        self.preseed_path = self.mkdtemp(override=filesystem.tftpd_dir())
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(IsoEmptyImage())
        # the preseed file needs to go into the dispatcher apache tmp directory.
        self.pipeline.add_action(
            DownloaderAction(
                "preseed", self.preseed_path, params=parameters["images"]["preseed"]
            )
        )
        self.pipeline.add_action(
            DownloaderAction("iso", self.mkdtemp(), params=parameters["images"]["iso"])
        )
        self.pipeline.add_action(IsoPullInstaller())
        self.pipeline.add_action(QemuCommandLine())
        # prepare overlay at this stage - make it available after installation.
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())  # idempotent, includes testdef
            self.pipeline.add_action(ApplyOverlayGuest())
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment())


class DeployIso(Deployment):
    name = "iso"

    @classmethod
    def action(cls):
        return DeployIsoAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "image" not in device["actions"]["deploy"]["methods"]:
            return False, '"image" is not in the device configuration deploy methods'
        if "to" in parameters and parameters["to"] == "iso-installer":
            if "iso" in parameters:
                if "installation_size" in parameters["iso"]:
                    return True, "accepted"
                else:
                    return False, '"installation_size" was not in the iso parameters'
            else:
                return False, '"iso" was not in the parameters'
        return False, '"to" was not in parameters, or "to" was not "iso-installer"'


class IsoEmptyImage(Action):
    name = "prepare-empty-image"
    description = "create empty image of specified size"
    summary = "create destination image"

    def __init__(self):
        super().__init__()
        self.size = 0

    def validate(self):
        super().validate()
        size_str = self.parameters["iso"]["installation_size"]
        if not isinstance(size_str, str):
            self.errors = "installation size needs to be a string, e.g. 2G or 800M"
            return
        size = size_str[:-1]
        if not size.isdigit():
            self.errors = "installation size needs to contain a digit, e.g. 2G or 800M"
            return
        if size_str.endswith("G"):
            self.size = int(size_str[:-1]) * 1024 * 1024 * 1024
        elif size_str.endswith("M"):
            self.size = int(size_str[:-1]) * 1024 * 1024
        else:
            self.errors = (
                "Unable to recognise size indication in %s - use M or G" % size_str
            )
        if self.size > INSTALLER_IMAGE_MAX_SIZE * 1024 * 1024:
            self.errors = (
                "Base installation size cannot exceed %s Mb" % INSTALLER_IMAGE_MAX_SIZE
            )

    def run(self, connection, max_end_time):
        # qemu-img create hd_img.img 2G
        base_dir = self.mkdtemp()
        output = os.path.join(base_dir, "hd.img")
        self.logger.info("Creating base image of size: %s bytes", self.size)
        prepare_install_base(output, self.size)
        self.set_namespace_data(
            action=self.name, label=self.name, key="output", value=output
        )
        self.results = {"success": output}
        return connection


class IsoPullInstaller(Action):
    """
    Take paths specified by the test writer to pull out
    of the specified iso so that necessary kernel options
    can be added to the default ISO boot commands.
    """

    name = "pull-installer-files"
    description = "pull kernel and initrd out of iso"
    summary = "copy files out of installer iso"

    FILE_KEYS = ["kernel", "initrd"]

    def __init__(self):
        super().__init__()
        self.files = {}

    def validate(self):
        super().validate()
        for key in self.FILE_KEYS:
            if key in self.parameters["iso"]:
                filename = self.parameters["iso"][key]
                if not filename.startswith("/"):
                    self.errors = (
                        "Paths to pull from the ISO need to start with / - check %s"
                        % key
                    )
                self.files[key] = filename
        if not self.valid:
            return
        unique_values = set()
        for key, value in self.files.items():
            unique_values.add(value)
            self.set_namespace_data(
                action=self.name,
                label=self.name,
                key=key,
                value=os.path.basename(value),
            )
        if len(unique_values) != len(self.files.values()):
            self.errors = "filenames to extract from installer image must be unique."

    def run(self, connection, max_end_time):
        """
        # cp ./iso/install.amd/vmlinuz vmlinuz
        # cp ./iso/install.amd/initrd.gz initrd.gz
        """
        # need download location
        iso_download = self.get_namespace_data(
            action="download-action", label="iso", key="file"
        )
        if not iso_download:
            raise JobError("installer image path is not present in the namespace.")
        destination = os.path.dirname(iso_download)
        copy_out_files(iso_download, list(self.files.values()), destination)
        for key, value in self.files.items():
            filename = os.path.join(destination, os.path.basename(value))
            self.logger.info("filename: %s size: %s", filename, os.stat(filename)[6])
            self.set_namespace_data(
                action=self.name, label=self.name, key=key, value=filename
            )
        self.results = {"success": list(self.files.values())}
        return connection


class QemuCommandLine(Action):
    name = "prepare-qemu-commands"
    description = "prepare qemu command and options to append to kernel command line"
    summary = "build qemu command line with kernel command string"

    def __init__(self):
        super().__init__()
        self.sub_command = []
        self.command_line = ""
        self.console = None
        self.boot_order = None
        self.preseed_file = None
        self.preseed_url = None

    def validate(self):
        super().validate()
        boot = self.job.device["actions"]["boot"]["methods"]["qemu"]
        qemu_binary = which(boot["parameters"]["command"])
        self.sub_command = [qemu_binary]
        self.sub_command.extend(boot["parameters"].get("options", []))
        boot_opts = boot["parameters"].get("boot_options")
        if boot_opts:
            self.console = "console=%s" % boot_opts["console"]
            self.boot_order = "-boot %s" % boot_opts["boot_order"]
        if not qemu_binary or not self.console or not self.boot_order:
            self.errors = "Invalid parameters for %s" % self.name
        # create the preseed.cfg url
        # needs to be an IP address for DI, DNS is not available.
        # PRESEED_URL='http://10.15.0.32/tmp/d-i/jessie/preseed.cfg'
        ip_addr = dispatcher_ip(self.job.parameters["dispatcher"], "tftp")
        self.preseed_url = "tftp://%s/" % ip_addr

        self.sub_command.append(" -drive format=raw,file={emptyimage} ")
        self.sub_command.append(self.boot_order)
        self.command_line = (
            " -append '%s console=tty0 console=tty1 %s %s %s %s preseed/url=%s{preseed} --- %s '  "
            % (
                self.parameters["deployment_data"]["base"],
                self.parameters["deployment_data"]["locale"],
                self.console,
                self.parameters["deployment_data"]["keymaps"],
                self.parameters["deployment_data"]["netcfg"],
                self.preseed_url,
                self.console,
            )
        )
        self.set_namespace_data(
            action=self.name,
            label=self.name,
            key="prompts",
            value=self.parameters["deployment_data"]["prompts"],
        )
        self.set_namespace_data(
            action=self.name, label=self.name, key="append", value=self.command_line
        )

    def run(self, connection, max_end_time):
        # include kernel and initrd from IsoPullInstaller
        kernel = self.get_namespace_data(
            action="pull-installer-files", label="pull-installer-files", key="kernel"
        )
        initrd = self.get_namespace_data(
            action="pull-installer-files", label="pull-installer-files", key="initrd"
        )
        self.sub_command.append(" -kernel %s " % kernel)
        self.sub_command.append(" -initrd %s " % initrd)
        self.set_namespace_data(
            action=self.name,
            label=self.name,
            key="sub_command",
            value=self.sub_command[:],
        )
        return connection
