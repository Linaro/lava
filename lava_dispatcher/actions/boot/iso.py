# Copyright (C) 2016 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import os

from lava_common.constants import INSTALLER_QUIET_MSG
from lava_common.exceptions import ConfigurationError, JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.shell import ExpectShellSession, ShellCommand, ShellSession
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.strings import substitute


class BootIsoInstaller(Boot):
    @classmethod
    def action(cls):
        return BootIsoInstallerAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "qemu-iso":
            return False, '"method" was not "qemu-iso"'
        if "media" not in parameters:
            return False, '"media" was not in parameters'
        if parameters["media"] != "img":
            return False, '"media" was not "img"'

        return True, "accepted"


class BootIsoInstallerAction(RetryAction):
    name = "boot-installer-iso"
    description = "boot installer with preseed"
    summary = "boot installer iso image"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(IsoCommandLine())
        self.pipeline.add_action(MonitorInstallerSession())
        self.pipeline.add_action(IsoRebootAction())
        # Add AutoLoginAction unconditionally as this action does nothing if
        # the configuration does not contain 'auto_login'
        self.pipeline.add_action(AutoLoginAction())
        self.pipeline.add_action(ExpectShellSession())
        self.pipeline.add_action(ExportDeviceEnvironment())


class IsoCommandLine(Action):

    """
    qemu-system-x86_64 -nographic -enable-kvm -cpu host -net nic,model=virtio,macaddr=52:54:00:12:34:59 -net user -m 2048 \
    -drive format=raw,file=hd_img.img -drive file=${NAME},index=2,media=cdrom,readonly \
    -boot c -no-reboot -kernel vmlinuz -initrd initrd.gz \
    -append "\"${BASE} ${LOCALE} ${CONSOLE} ${KEYMAPS} ${NETCFG} preseed/url=${PRESEED_URL} --- ${CONSOLE}\"" \
    """

    name = "execute-installer-command"
    description = "add dynamic data values to command line and execute"
    summary = "include downloaded locations and call qemu"

    def run(self, connection, max_end_time):
        # substitutions
        substitutions = {
            "{emptyimage}": self.get_namespace_data(
                action="prepare-empty-image", label="prepare-empty-image", key="output"
            )
        }
        sub_command = self.get_namespace_data(
            action="prepare-qemu-commands",
            label="prepare-qemu-commands",
            key="sub_command",
        )
        sub_command = substitute(sub_command, substitutions)
        command_line = " ".join(sub_command)

        commands = []
        # get the download args in run()
        image_arg = self.get_namespace_data(
            action="download-action", label="iso", key="image_arg"
        )
        action_arg = self.get_namespace_data(
            action="download-action", label="iso", key="file"
        )
        substitutions["{%s}" % "iso"] = action_arg
        commands.append(image_arg)
        command_line += " ".join(substitute(commands, substitutions))

        preseed_file = self.get_namespace_data(
            action="download-action", label="file", key="preseed"
        )
        if not preseed_file:
            raise JobError("Unable to identify downloaded preseed filename.")
        substitutions = {"{preseed}": preseed_file}
        append_args = self.get_namespace_data(
            action="prepare-qemu-commands", label="prepare-qemu-commands", key="append"
        )
        append_args = substitute([append_args], substitutions)
        command_line += " ".join(append_args)

        self.logger.info(command_line)
        shell = ShellCommand(command_line, self.timeout, logger=self.logger)
        if shell.exitstatus:
            raise JobError(
                "%s command exited %d: %s"
                % (sub_command[0], shell.exitstatus, shell.readlines())
            )
        self.logger.debug("started a shell command")

        shell_connection = ShellSession(self.job, shell)
        shell_connection.prompt_str = self.get_namespace_data(
            action="prepare-qemu-commands", label="prepare-qemu-commands", key="prompts"
        )
        shell_connection = super().run(shell_connection, max_end_time)
        return shell_connection


class MonitorInstallerSession(Action):
    """
    Waits for a shell connection to the device for the current job.
    The shell connection can be over any particular connection,
    all that is needed is a prompt.
    """

    name = "monitor-installer-connection"
    description = "Monitor installer operation"
    summary = "Watch for error strings or end of install"

    def __init__(self):
        super().__init__()
        self.force_prompt = True

    def validate(self):
        super().validate()
        if "prompts" not in self.parameters:
            self.errors = "Unable to identify test image prompts from parameters."

    def run(self, connection, max_end_time):
        self.logger.debug(
            "%s: Waiting for prompt %s", self.name, " ".join(connection.prompt_str)
        )
        self.wait(connection, max_end_time)
        return connection


class IsoRebootAction(Action):
    name = "reboot-into-installed"
    description = "reboot and login to the new system"
    summary = "reboot into installed image"

    def __init__(self):
        super().__init__()
        self.sub_command = None

    def validate(self):
        super().validate()
        if "prompts" not in self.parameters:
            self.errors = "Unable to identify boot prompts from job definition."
        try:
            boot = self.job.device["actions"]["boot"]["methods"]["qemu"]
            qemu_binary = which(boot["parameters"]["command"])
            self.sub_command = [qemu_binary]
            self.sub_command.extend(boot["parameters"].get("options", []))
        except AttributeError as exc:
            raise ConfigurationError(exc)
        except (KeyError, TypeError):
            self.errors = "Invalid parameters for %s" % self.name

    def run(self, connection, max_end_time):
        """
        qemu needs help to reboot after running the debian installer
        and typically the boot is quiet, so there is almost nothing to log.
        """
        base_image = self.get_namespace_data(
            action="prepare-empty-image", label="prepare-empty-image", key="output"
        )
        self.sub_command.append("-drive format=raw,file=%s" % base_image)
        guest = self.get_namespace_data(
            action="apply-overlay-guest", label="guest", key="filename"
        )
        if guest:
            self.logger.info("Extending command line for qcow2 test overlay")
            self.sub_command.append(
                "-drive format=qcow2,file=%s,media=disk" % (os.path.realpath(guest))
            )
            # push the mount operation to the test shell pre-command to be run
            # before the test shell tries to execute.
            shell_precommand_list = []
            mountpoint = self.get_namespace_data(
                action="test", label="results", key="lava_test_results_dir"
            )
            shell_precommand_list.append("mkdir %s" % mountpoint)
            shell_precommand_list.append("mount -L LAVA %s" % mountpoint)
            self.set_namespace_data(
                action="test",
                label="lava-test-shell",
                key="pre-command-list",
                value=shell_precommand_list,
            )

        self.logger.info("Boot command: %s", " ".join(self.sub_command))
        shell = ShellCommand(
            " ".join(self.sub_command), self.timeout, logger=self.logger
        )
        if shell.exitstatus:
            raise JobError(
                "%s command exited %d: %s"
                % (self.sub_command, shell.exitstatus, shell.readlines())
            )
        self.logger.debug("started a shell command")

        shell_connection = ShellSession(self.job, shell)
        shell_connection = super().run(shell_connection, max_end_time)
        shell_connection.prompt_str = [INSTALLER_QUIET_MSG]
        self.wait(shell_connection)
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=shell_connection
        )
        return shell_connection
