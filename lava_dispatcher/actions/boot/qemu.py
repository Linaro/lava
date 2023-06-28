# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import shlex
import subprocess

from lava_common.constants import DISPATCHER_DOWNLOAD_DIR, SYS_CLASS_KVM
from lava_common.exceptions import JobError
from lava_common.utils import debian_package_arch, debian_package_version
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, BootHasMixin, OverlayUnpack
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.serial import QemuSession
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.shell import ExpectShellSession, ShellCommand
from lava_dispatcher.utils.docker import DockerRun
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.strings import substitute


class BootQEMU(Boot):
    """
    The Boot method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then allow AutoLogin, if
    enabled, and then expect a shell session which can be handed over to the
    test method. self.run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    compatibility = 4

    @classmethod
    def action(cls):
        return BootQEMUImageAction()

    @classmethod
    def accepts(cls, device, parameters):
        methods = device["actions"]["boot"]["methods"]
        if "qemu" not in methods and "qemu-nfs" not in methods:
            return (
                False,
                '"qemu" or "qemu-nfs" was not in the device configuration boot methods',
            )
        if "method" not in parameters:
            return False, '"method" was not in parameters'
        if parameters["method"] not in ["qemu", "qemu-nfs", "monitor"]:
            return False, '"method" was not "qemu" or "qemu-nfs"'
        return True, "accepted"


class BootQEMUImageAction(BootHasMixin, RetryAction):
    name = "boot-image-retry"
    description = "boot image with retry"
    summary = "boot with retry"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(BootQemuRetry())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack())
                self.pipeline.add_action(ExportDeviceEnvironment())


class BootQemuRetry(RetryAction):
    name = "boot-qemu-image"
    description = "boot image using QEMU command line"
    summary = "boot QEMU image"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(CallQemuAction())


class CallQemuAction(Action):
    name = "execute-qemu"
    description = "call qemu to boot the image"
    summary = "execute qemu to boot the image"

    session_class = QemuSession
    shell_class = ShellCommand

    def __init__(self):
        super().__init__()
        self.base_sub_command = []
        self.docker = None
        self.sub_command = []
        self.commands = []
        self.methods = None
        self.nfsrootfs = None
        self.qemu_data = {}

    def get_qemu_pkg_suffix(self, arch):
        if arch in ["amd64", "x86_64"]:
            return "x86"
        if arch in ["arm64", "arm", "armhf", "aarch64"]:
            return "arm"
        return ""

    def get_debian_version(self, architecture):
        pkg_suffix = self.get_qemu_pkg_suffix(architecture)
        if pkg_suffix == "":
            return False
        if "docker" in self.parameters:
            # We will find it by get_raw_version()
            return False
        ver_str = debian_package_version(pkg="qemu-system-%s" % pkg_suffix)
        arch_str = debian_package_arch(pkg="qemu-system-%s" % pkg_suffix)
        if ver_str == "":
            return False
        self.qemu_data = {
            "qemu_version": ver_str,
            "host_arch": arch_str,
            "job_arch": architecture,
        }
        self.logger.info(
            "qemu-system-%s, installed at version: %s, host architecture: %s",
            pkg_suffix,
            ver_str,
            arch_str,
        )
        return True

    def get_qemu_arch(self, architecture):
        if architecture == "arm64":
            return "aarch64"
        return architecture

    def get_raw_version(self, architecture):
        if "docker" in self.parameters:
            docker = DockerRun.from_parameters(self.parameters["docker"], self.job)
            docker.run(
                *shlex.split(
                    "qemu-system-%s --version" % self.get_qemu_arch(architecture)
                ),
                action=self
            )
            return True
        ver_strs = subprocess.check_output(
            ("qemu-system-%s" % architecture, "--version")
        )
        # line is QEMU emulator version xxxx
        ver_str = ver_strs.split()[3].decode("utf-8", errors="replace")
        arch_str = (
            subprocess.check_output(("uname", "-m"))
            .strip()
            .decode("utf-8", errors="replace")
        )
        self.qemu_data = {
            "qemu_version": ver_str,
            "host_arch": arch_str,
            "job_arch": architecture,
        }
        self.logger.info(
            "qemu, installed at version: %s, host architecture: %s", ver_str, arch_str
        )
        return True

    def validate(self):
        super().validate()

        # 'arch' must be defined in job definition context.
        architecture = self.job.parameters.get("context", {}).get("arch")
        if architecture is None:
            raise JobError("Missing 'arch' in job context")
        if "available_architectures" not in self.job.device:
            self.errors = "Device lacks list of available architectures."
        try:
            if architecture not in self.job.device["available_architectures"]:
                self.errors = "Non existing architecture specified in context arch parameter. Please check the device configuration for available options."
                return
        except KeyError:
            self.errors = "Arch parameter must be set in the context section. Please check the device configuration for available architectures."
            return

        if not self.get_debian_version(architecture):
            self.get_raw_version(architecture)

        if self.parameters["method"] in ["qemu", "qemu-nfs"]:
            if "prompts" not in self.parameters:
                if self.test_has_shell(self.parameters):
                    self.errors = "Unable to identify boot prompts from job definition."
        self.methods = self.job.device["actions"]["boot"]["methods"]
        method = self.parameters["method"]
        boot = (
            self.methods["qemu"] if "qemu" in self.methods else self.methods["qemu-nfs"]
        )
        try:
            if "parameters" not in boot or "command" not in boot["parameters"]:
                self.errors = "Invalid device configuration - missing parameters"
            elif not boot["parameters"]["command"]:
                self.errors = "No QEMU binary command found - missing context."
            # if qemu is ran under docker, qemu could not be installed and so which will fail
            qemu_binary = boot["parameters"]["command"]
            if "docker" not in self.parameters:
                qemu_binary = which(qemu_binary)
            self.base_sub_command = [qemu_binary]
            self.base_sub_command.extend(boot["parameters"].get("options", []))
            self.base_sub_command.extend(
                ["%s" % item for item in boot["parameters"].get("extra", [])]
            )
        except AttributeError as exc:
            self.errors = "Unable to parse device options: %s %s" % (
                exc,
                self.job.device["actions"]["boot"]["methods"][method],
            )
        except (KeyError, TypeError):
            self.errors = "Invalid parameters for %s" % self.name

        for label in self.get_namespace_keys("download-action"):
            if label in ["offset", "available_loops", "uefi", "nfsrootfs"]:
                continue
            image_arg = self.get_namespace_data(
                action="download-action", label=label, key="image_arg"
            )
            action_arg = self.get_namespace_data(
                action="download-action", label=label, key="file"
            )
            if not image_arg or not action_arg:
                self.logger.warning("Missing image arg for %s", label)
                continue
            self.commands.append(image_arg)

        # Check for enable-kvm command line option in device configuration.
        if method not in self.job.device["actions"]["boot"]["methods"]:
            self.errors = "Unknown boot method '%s'" % method
            return

        options = self.job.device["actions"]["boot"]["methods"][method]["parameters"][
            "options"
        ]
        if "-enable-kvm" in options:
            # Check if the worker has kvm enabled.
            if not os.path.exists(SYS_CLASS_KVM):
                self.errors = "Device configuration contains -enable-kvm option but kvm module is not enabled."

    def run(self, connection, max_end_time):
        """
        CommandRunner expects a pexpect.spawn connection which is the return value
        of target.device.power_on executed by boot in the old dispatcher.

        In the new pipeline, the pexpect.spawn is a ShellCommand and the
        connection is a ShellSession. CommandRunner inside the ShellSession
        turns the ShellCommand into a runner which the ShellSession uses via ShellSession.run()
        to run commands issued *after* the device has booted.
        pexpect.spawn is one of the raw_connection objects for a Connection class.
        """
        if connection:
            ns_connection = self.get_namespace_data(
                action="shared", label="shared", key="connection", deepcopy=False
            )
            if connection == ns_connection:
                connection.finalise()

        self.sub_command = self.base_sub_command.copy()
        # Generate the sub command
        substitutions = {}
        for label in self.get_namespace_keys("download-action"):
            if label in ["offset", "available_loops", "uefi", "nfsrootfs"]:
                continue
            image_arg = self.get_namespace_data(
                action="download-action", label=label, key="image_arg"
            )
            action_arg = self.get_namespace_data(
                action="download-action", label=label, key="file"
            )
            if image_arg is not None:
                substitutions["{%s}" % label] = action_arg
        substitutions["{NFS_SERVER_IP}"] = dispatcher_ip(
            self.job.parameters["dispatcher"], "nfs"
        )
        self.sub_command.extend(substitute(self.commands, substitutions))
        uefi_dir = self.get_namespace_data(
            action="deployimages", label="image", key="uefi_dir"
        )
        if uefi_dir:
            self.sub_command.extend(["-L", uefi_dir, "-monitor", "none"])

        # initialise the first Connection object, a command line shell into the running QEMU.
        self.results = self.qemu_data
        guest = self.get_namespace_data(
            action="apply-overlay-guest", label="guest", key="filename"
        )
        applied = self.get_namespace_data(
            action="append-overlays", label="guest", key="applied"
        )

        # check for NFS
        if "qemu-nfs" == self.parameters["method"]:
            self.logger.debug("Adding NFS arguments to kernel command line.")
            root_dir = self.get_namespace_data(
                action="extract-rootfs", label="file", key="nfsroot"
            )
            substitutions["{NFSROOTFS}"] = root_dir
            params = self.methods["qemu-nfs"]["parameters"]["append"]
            # console=ttyAMA0 root=/dev/nfs nfsroot=10.3.2.1:/var/lib/lava/dispatcher/tmp/dirname,tcp,hard,intr ip=dhcp
            append = [
                "console=%s" % params["console"],
                "root=/dev/nfs",
                "%s rw" % substitute([params["nfsrootargs"]], substitutions)[0],
                "%s" % params["ipargs"],
            ]
            self.sub_command.append("--append")
            self.sub_command.append('"%s"' % " ".join(append))
        elif guest and not applied:
            self.logger.info("Extending command line for qcow2 test overlay")
            # interface is ide by default in qemu
            interface = self.job.device["actions"]["deploy"]["methods"]["image"][
                "parameters"
            ]["guest"].get("interface", "ide")
            driveid = self.job.device["actions"]["deploy"]["methods"]["image"][
                "parameters"
            ]["guest"].get("driveid", "lavatest")
            self.sub_command.append(
                "-drive format=qcow2,file=%s,media=disk,if=%s,id=%s"
                % (os.path.realpath(guest), interface, driveid)
            )
            # push the mount operation to the test shell pre-command to be run
            # before the test shell tries to execute.
            shell_precommand_list = []
            mountpoint = self.get_namespace_data(
                action="test", label="results", key="lava_test_results_dir"
            )
            uuid = "/dev/disk/by-uuid/%s" % self.get_namespace_data(
                action="apply-overlay-guest", label="guest", key="UUID"
            )
            shell_precommand_list.append("mkdir %s" % mountpoint)
            # prepare_guestfs always uses ext2
            shell_precommand_list.append("mount %s -t ext2 %s" % (uuid, mountpoint))
            # debug line to show the effect of the mount operation
            # also allows time for kernel messages from the mount operation to be processed.
            shell_precommand_list.append("ls -la %s/bin/lava-test-runner" % mountpoint)
            self.set_namespace_data(
                action="test",
                label="lava-test-shell",
                key="pre-command-list",
                value=shell_precommand_list,
            )

        if "docker" in self.parameters:
            self.docker = docker = DockerRun.from_parameters(
                self.parameters["docker"], self.job
            )
            if not self.parameters["docker"].get("container_name"):
                docker.name(
                    "lava-docker-qemu-%s-%s-" % (self.job.job_id, self.level),
                    random_suffix=True,
                )
            docker.interactive()
            docker.tty()
            if "QEMU_AUDIO_DRV" in os.environ:
                docker.environment("QEMU_AUDIO_DRV", os.environ["QEMU_AUDIO_DRV"])
            docker.bind_mount(DISPATCHER_DOWNLOAD_DIR)
            docker.add_device("/dev/kvm", skip_missing=True)
            docker.add_device("/dev/net/tun", skip_missing=True)
            docker.add_docker_run_options("--network=host", "--cap-add=NET_ADMIN")

            # Use docker.binary if provided and fallback to the qemu default binary
            args = [self.parameters["docker"].get("binary", self.sub_command[0])]

            self.logger.info("Pulling docker image")
            docker.prepare(action=self)
            self.sub_command[0] = " ".join(docker.cmdline(*args))

        self.logger.info("Boot command: %s", " ".join(self.sub_command))
        shell = self.shell_class(
            " ".join(self.sub_command), self.timeout, logger=self.logger
        )
        if shell.exitstatus:
            raise JobError(
                "%s command exited %d: %s"
                % (self.sub_command, shell.exitstatus, shell.readlines())
            )
        self.logger.debug("started a shell command")

        shell_connection = self.session_class(self.job, shell)
        shell_connection = super().run(shell_connection, max_end_time)

        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=shell_connection
        )
        return shell_connection

    def cleanup(self, connection):
        if self.docker is not None:
            self.logger.info("Stopping the qemu container %s", self.docker.__name__)
            self.docker.destroy()


# FIXME: implement a QEMU protocol to monitor VM boots
