# Copyright (C) 2016 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Action, JobError
from lava_dispatcher.shell import ShellCommand, ShellSession
from lava_dispatcher.utils.shell import which


class LxcSession(ShellSession):
    """Extends a ShellSession to include the ability to disconnect and finalise
    cleanly.
    """

    name = "LxcSession"

    def finalise(self):
        self.disconnect("closing")
        super().finalise()

    def disconnect(self, reason=""):
        self.sendline("exit", disconnecting=True)
        self.connected = False


class ConnectLxc(Action):
    """
    Class to make a lxc shell connection to the container.
    """

    name = "connect-lxc"
    description = "connect to the lxc container"
    summary = "run connection command"

    session_class = LxcSession
    shell_class = ShellCommand

    def validate(self):
        if "lxc" not in self.job.device["actions"]["boot"]["methods"]:
            return
        super().validate()
        which("lxc-attach")
        if "lxc" not in self.job.device["actions"]["boot"]["connections"]:
            self.errors = "Device not configured to support LXC connection."

    def run(self, connection, max_end_time):
        lxc_name = self.get_namespace_data(
            action="lxc-create-action", label="lxc", key="name"
        )
        if not lxc_name:
            self.logger.debug("No LXC device requested")
            return connection

        connection = self.get_namespace_data(
            action="shared", label="shared", key="connection", deepcopy=False
        )
        if connection:
            return connection

        cmd = f"lxc-attach -n {lxc_name}"
        self.logger.info("%s Connecting to device using '%s'", self.name, cmd)
        # ShellCommand executes the connection command
        shell = self.shell_class(
            "%s\n" % cmd,
            self.timeout,
            logger=self.logger,
            window=self.job.device.get_constant("spawn_maxread"),
        )
        if shell.exitstatus:
            raise JobError(
                "%s command exited %d: %s" % (cmd, shell.exitstatus, shell.readlines())
            )
        # LxcSession monitors the pexpect
        connection = self.session_class(self.job, shell)
        connection.connected = True
        connection = super().run(connection, max_end_time)
        connection.prompt_str = self.parameters["prompts"]
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection
