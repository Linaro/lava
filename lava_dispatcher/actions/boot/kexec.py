# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from lava_common.constants import DISPATCHER_DOWNLOAD_DIR
from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, OverlayUnpack
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.network import dispatcher_ip


class BootKExec(Boot):
    """
    Expects a shell session, checks for kexec executable and
    prepares the arguments to run kexec,
    """

    @classmethod
    def action(cls):
        return BootKexecAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "kexec":
            return False, '"method" was not "kexec"'

        return True, "accepted"


class BootKexecAction(RetryAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the connection after boot
    """

    name = "kexec-boot"
    summary = "kexec a new kernel"
    description = "replace current kernel using kexec"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(KexecAction())
        # Add AutoLoginAction unconditionally as this action does nothing if
        # the configuration does not contain 'auto_login'
        self.pipeline.add_action(AutoLoginAction())
        self.pipeline.add_action(ExpectShellSession())
        if "transfer_overlay" in parameters:
            self.pipeline.add_action(OverlayUnpack())
        self.pipeline.add_action(ExportDeviceEnvironment())


class KexecAction(Action):
    """
    The files need to have been downloaded by a previous test action.
    This action calls kexec to load the kernel ,execute it and then
    attempts to reestablish the shell connection after boot.
    """

    name = "call-kexec"
    summary = "attempt to kexec new kernel"
    description = "call kexec with specified arguments"

    def __init__(self):
        super().__init__()
        self.command = ""
        self.load_command = ""
        self.deploy_commands = []

    def append_deploy_cmd(self, key, ip_addr):
        if key not in self.parameters:
            return

        path = self.get_namespace_data(action="download-action", label=key, key="file")
        if path is None:
            raise JobError(f"Missing '{key}' in deploy stage")

        path = path[len(DISPATCHER_DOWNLOAD_DIR) + 1 :]
        cmd = f"wget http://{ip_addr}/tmp/{path} -O {self.parameters[key]}"
        self.deploy_commands.append(cmd)

    def validate(self):
        super().validate()
        self.command = self.parameters.get("command", "/sbin/kexec")
        self.load_command = self.command[:]  # local copy for idempotency

        if self.parameters.get("deploy", False):
            initrd_path = self.get_namespace_data(
                action="download-action", label="initrd", key="file"
            )
            ip_addr = dispatcher_ip(self.job.parameters["dispatcher"], "http")

            self.append_deploy_cmd("kernel", ip_addr)
            self.append_deploy_cmd("initrd", ip_addr)
            self.append_deploy_cmd("dtb", ip_addr)
            self.logger.debug("deploy commands:")
            for cmd in self.deploy_commands:
                self.logger.info("- %s", cmd)

        # If on_panic is set, crash the kernel instead of calling "kexec -e"
        if self.parameters.get("on_panic", False):
            self.command = "echo c > /proc/sysrq-trigger"
        else:
            self.command += " -e"

        # If on_panic is set, use --load-panic instead of --load
        if "kernel" in self.parameters:
            if self.parameters.get("on_panic", False):
                self.load_command += " --load-panic %s" % self.parameters["kernel"]
            else:
                self.load_command += " --load %s" % self.parameters["kernel"]

        if "dtb" in self.parameters:
            self.load_command += " --dtb %s" % self.parameters["dtb"]
        if "initrd" in self.parameters:
            self.load_command += " --initrd %s" % self.parameters["initrd"]
        if "options" in self.parameters:
            for option in self.parameters["options"]:
                self.load_command += " %s" % option
        if self.load_command == "/sbin/kexec":
            self.errors = "Default kexec handler needs at least a kernel to pass to the --load command"

    def run(self, connection, max_end_time):
        """
        If kexec fails, there is no real chance at diagnostics because the device will be hung.
        Get the output prior to the call, in case this helps after the job fails.
        """
        connection = super().run(connection, max_end_time)

        if self.deploy_commands:
            self.logger.debug("Running deploy commands")
        for cmd in self.deploy_commands:
            connection.sendline(cmd, delay=self.character_delay)
            self.wait(connection)

        if "kernel-config" in self.parameters:
            cmd = "zgrep -i kexec %s |grep -v '^#'" % self.parameters["kernel-config"]
            self.logger.debug("Checking for kexec: %s", cmd)
            connection.sendline(cmd, delay=self.character_delay)
            self.wait(connection)
        connection.sendline(self.load_command, delay=self.character_delay)
        self.wait(connection)
        connection.sendline(self.command, delay=self.character_delay)
        connection.prompt_str = self.parameters["boot_message"]
        connection.wait()
        return connection
