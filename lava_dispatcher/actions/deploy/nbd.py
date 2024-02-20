# Copyright (C) 2017 The Linux Foundation
#
# Author: Jan-Simon Moeller <jsmoeller@linuxfoundation.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os
import re
import shutil
import tempfile
from pathlib import Path

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.actions.deploy.prepare import PrepareKernelAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.protocols.xnbd import XnbdProtocol
from lava_dispatcher.utils import filesystem
from lava_dispatcher.utils.shell import which


class Nbd(Deployment):
    """
    Strategy class for a tftp+initrd+nbd based Deployment.
    tftp is used for kernel/initrd/fdt. Rootfs over nbd (network block device).
    Downloads the relevant parts, copies to the tftp location.
    Limited to what the bootloader can deploy which means ramdisk or nfsrootfs.
    rootfs deployments would format the device and create a single partition for the rootfs.
    """

    name = "nbd"

    @classmethod
    def action(cls):
        return NbdAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "nbd":
            return False, '"to" parameter is not "nbd"'
        if "nbd" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"ndb" was not in the device configuration deploy methods'


class NbdAction(Action):
    name = "nbd-deploy"
    description = "download files and deploy for using tftp+initrd+nbd"
    summary = "nbd deployment"

    def __init__(self):
        super().__init__()
        self.tftp_dir = None
        self.nbd_ip = None
        self.nbd_port = None

    def validate(self):
        super().validate()
        if "kernel" not in self.parameters:
            self.errors = "%s needs a kernel to deploy" % self.name
        if not self.valid:
            return
        if "nbdroot" not in self.parameters:
            self.errors = "NBD deployment needs a 'nbdroot' parameter"
        if "initrd" not in self.parameters:
            self.errors = "NBD deployment needs an 'initrd' parameter"
        # we cannot work with these when using nbd
        if "nfsrootfs" in self.parameters:
            self.errors = "nfsrootfs cannot be used with NBD deployment, use a e.g. ext3/4 filesystem as 'nbdroot=' parameter"
        if "ramdisk" in self.parameters:
            self.errors = "ramdisk cannot be used with NBD deployment, use a e.g. ext3/4 filesystem as 'initrd' parameter"

        # Extract the 3 last path elements. See action.mkdtemp()
        suffix = os.path.join(*self.tftp_dir.split("/")[-2:])
        self.set_namespace_data(
            action="tftp-deploy", label="tftp", key="suffix", value=suffix
        )
        # we need tftp _and_ nbd-server
        which("in.tftpd")
        which("nbd-server")

        # Check that the tmp directory is in the nbdd_dir or in /tmp for the
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
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.set_namespace_data(
            action=self.name,
            label="tftp",
            key="tftp_dir",
            value=self.tftp_dir,
            parameters=parameters,
        )

        for key in ["initrd", "kernel", "dtb", "nbdroot"]:
            if key in parameters:
                download = DownloaderAction(
                    key, path=self.tftp_dir, params=parameters[key]
                )
                download.max_retries = (
                    3  # overridden by failure_retry in the parameters, if set.
                )
                self.pipeline.add_action(download)
                if key == "initrd":
                    self.set_namespace_data(
                        action="tftp-deploy",
                        label="tftp",
                        key="ramdisk",
                        value=True,
                        parameters=parameters,
                    )
                    self.set_namespace_data(
                        action=self.name,
                        label="nbd",
                        key="initrd",
                        value=True,
                        parameters=parameters,
                    )

        # prepare overlay
        self.pipeline.add_action(OverlayAction())
        if "kernel" in parameters and "type" in parameters["kernel"]:
            self.pipeline.add_action(PrepareKernelAction())
        # setup values for protocol and later steps
        self.set_namespace_data(
            action=self.name,
            label="nbd",
            key="initrd",
            value=True,
            parameters=parameters,
        )
        # store in parameters for protocol 'xnbd' to tear-down nbd-server
        # and store in namespace for boot action
        # ip
        parameters["lava-xnbd"] = {}
        # handle XnbdAction next - bring-up nbd-server
        self.pipeline.add_action(XnbdAction())


class XnbdAction(Action):
    name = "xnbd-server-deploy"
    description = "nbd daemon"
    summary = "nbd daemon"

    def __init__(self):
        super().__init__()
        self.protocol = XnbdProtocol.name
        self.nbd_server_port = None
        self.nbd_server_ip = None

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        self.logger.debug("%s: starting nbd-server", self.name)
        # pull from parameters - as previously set
        self.nbd_root = self.parameters["lava-xnbd"]["nbdroot"]
        self.nbd_server_port = self.get_namespace_data(
            action="nbd-deploy", label="nbd", key="nbd_server_port"
        )
        self.nbd_server_ip = self.get_namespace_data(
            action="nbd-deploy", label="nbd", key="nbd_server_ip"
        )
        if self.nbd_server_port is None:
            self.errors = "NBD server port is unset"
            return connection
        self.logger.debug(
            "NBD-IP: %s, NBD-PORT: %s, NBD-ROOT: %s",
            self.nbd_server_ip,
            self.nbd_server_port,
            self.nbd_root,
        )
        if re.search(filesystem.tftpd_dir(), self.nbd_root):
            fullpath_nbdroot = self.nbd_root
        else:
            fullpath_nbdroot = "%s/%s" % (
                os.path.realpath(filesystem.tftpd_dir()),
                self.nbd_root,
            )
        # on debian, nbd-server change user to nbd
        if os.path.exists("/etc/nbd-server/config"):
            data = Path("/etc/nbd-server/config").read_text(encoding="utf-8")
            # user will always be on the second line at minimum due to [generic] header
            ret = re.search(r"\n\s*user\s*=\s*([a-z0-9_-]+)", data)
            if ret and ret.lastindex == 1:
                self.logger.debug("NBD server will be running as %s" % ret.group(1))
                shutil.chown(fullpath_nbdroot, user=ret.group(1))

        nbd_cmd = [
            "nbd-server",
            "%s" % self.nbd_server_port,
            fullpath_nbdroot,
        ]
        command_output = self.run_command(nbd_cmd, allow_fail=False)

        if command_output and "error" in command_output:
            raise JobError("nbd-server: %s" % command_output)
        else:
            self.logger.debug("%s: starting nbd-server done", self.name)
        return connection
