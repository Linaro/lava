# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from lava_dispatcher.connection import RECOGNIZED_TAGS
from lava_dispatcher.utils.shell import which
from lava_dispatcher.action import Action
from lava_common.exceptions import JobError, InfrastructureError
from lava_dispatcher.shell import ShellCommand, ShellSession


class ConnectDevice(Action):
    """
    General purpose class to use the device commands to
    make a serial connection to the device. e.g. using ser2net
    Inherit from this class and change the session_class and/or shell_class for different behaviour.
    """

    name = "connect-device"
    description = "use the configured command to connect serial to the device"
    summary = "run connection command"
    timeout_exception = InfrastructureError

    # wraps the pexpect and provides prompt_str access
    session_class = ShellSession
    # runs the command to initiate the connection
    shell_class = ShellCommand

    def __init__(self):
        super().__init__()
        self.command = ""
        self.hardware = None
        self.primary = True
        self.message = "Connecting to device using"
        self.tag_dict = {}

    def _check_command(self):
        exe = ""
        try:
            exe = self.command.split(" ")[0]
        except AttributeError:
            self.errors = "Unable to parse the connection command %s" % self.command
        which(exe)

    def validate(self):
        super().validate()
        matched = False
        if "serial" not in self.job.device["actions"]["boot"]["connections"]:
            self.errors = "Device not configured to support serial connection."
        if "commands" not in self.job.device:
            self.errors = "Invalid device configuration - missing 'commands'"
            return
        if "connect" in self.job.device["commands"]:
            # deprecated but allowed for primary
            if self.primary:
                self.command = self.job.device["commands"]["connect"][
                    :
                ]  # local copy to retain idempotency.
            else:
                self.errors = "Device configuration retains deprecated connect command."
        elif "connections" in self.job.device["commands"]:
            # if not primary, takes account of the name from the job definition
            for hardware, value in self.job.device["commands"]["connections"].items():
                if "connect" not in value:
                    self.errors = "Misconfigured connection commands"
                    return
                if self.primary:
                    if "primary" in value.get("tags", []):
                        self.hardware = hardware
                        self.tag_dict[hardware] = value.get("tags", [])
                        break
                else:
                    if "tags" in value:
                        if "primary" in value["tags"]:
                            # ignore any primary hardware
                            continue
                        else:
                            # allow tags other than primary
                            if hardware == self.hardware:
                                matched = True
                                self.tag_dict[hardware] = value.get("tags", [])
                                break
                    else:
                        # allow for no tags
                        matched = True
                        self.tag_dict[hardware] = value.get("tags", [])
                        break
            if self.primary:
                if not self.hardware:
                    self.errors = "Unable to identify primary connection command."
            else:
                if not matched:
                    self.errors = (
                        "Unable to identify connection command hardware. %s"
                        % self.hardware
                    )
            self.command = self.job.device["commands"]["connections"][self.hardware][
                "connect"
            ][
                :
            ]  # local copy to retain idempotency.
        self._check_command()

    def run(self, connection, max_end_time):
        connection_namespace = self.parameters.get("connection-namespace")
        parameters = None
        if connection_namespace:
            parameters = {"namespace": connection_namespace}
        else:
            parameters = {"namespace": self.parameters.get("namespace", "common")}
        connection = self.get_namespace_data(
            action="shared",
            label="shared",
            key="connection",
            deepcopy=False,
            parameters=parameters,
        )
        if connection:
            if connection.connected:
                self.logger.debug("Already connected")
                # Save the connection in the current namespace
                self.set_namespace_data(
                    action="shared", label="shared", key="connection", value=connection
                )
                return connection
            else:
                self.logger.info("Dead connection, reconnecting")

        if connection_namespace:
            self.logger.warning(
                "connection_namespace provided but no connection found. "
                "Please ensure that this parameter is correctly set to existing namespace."
            )
            raise JobError(
                "Unable to reuse connection from namespace '%s'" % connection_namespace
            )

        self.logger.info(
            "[%s] %s %s '%s'",
            parameters["namespace"],
            self.name,
            self.message,
            self.command,
        )
        # ShellCommand executes the connection command
        shell = self.shell_class(
            "%s\n" % self.command,
            self.timeout,
            logger=self.logger,
            window=self.job.device.get_constant("spawn_maxread"),
        )
        if shell.exitstatus:
            raise InfrastructureError(
                "%s command exited %d: %s"
                % (self.command, shell.exitstatus, shell.readlines())
            )
        # ShellSession monitors the pexpect
        connection = self.session_class(self.job, shell)
        connection.connected = True
        if self.hardware:
            connection.tags = self.tag_dict[self.hardware]
        connection = super().run(connection, max_end_time)
        if not connection.prompt_str:
            connection.prompt_str = [
                self.job.device.get_constant("default-shell-prompt")
            ]
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection


class ConnectShell(ConnectDevice):
    """
    Specialist class to use the device commands to connect to the
    kernel console, e.g. using ser2net
    """

    # wraps the pexpect and provides prompt_str access
    session_class = ShellSession
    # runs the command to initiate the connection
    shell_class = ShellCommand

    def __init__(self, name=None):
        super().__init__()
        self.name = "connect-shell"
        self.primary = False
        self.hardware = name
        self.summary = "run connection command"
        self.description = (
            "use the configured command to connect serial to a second shell"
        )
        self.message = "Connecting to shell using"

    def validate(self):
        super().validate()
        if "connections" not in self.job.device["commands"]:
            self.errors = "Unable to connect to shell - missing connections block."
            return
        self._check_command()

    def run(self, connection, max_end_time):
        # explicitly call the base class run()
        connection = super().run(connection, max_end_time)
        self.logger.debug("Forcing a prompt")
        # force a prompt to appear without using a character that could be interpreted as a username
        connection.sendline("")
        return connection


class QemuSession(ShellSession):
    """Extends a ShellSession to include the ability to disconnect and finalise
    cleanly.
    """

    name = "QemuSession"

    def __init__(self, job, raw_connection):
        super().__init__(job, raw_connection)
        self.tags = ["qemu"]

    def finalise(self):
        self.disconnect("closing")
        super().finalise()

    def disconnect(self, reason=""):
        self.sendline("poweroff", disconnecting=True)
        self.listen_feedback(5)
        self.connected = False
        super().disconnect()


class DisconnectDevice(ConnectDevice):
    """
    Breaks the serial connection made by ConnectDevice.
    """

    def __init__(self):
        super().__init__()
        self.name = "disconnect-device"
        self.description = "disconnect from console"
        self.summary = self.description

    def validate(self):
        super().validate()
        if "connections" not in self.job.device["commands"]:
            self.errors = "Unable to connect to shell - missing connections block."
            return
        primary_connection_has_correct_tags = False
        for connection in self.job.device["commands"]["connections"]:
            tags = self.job.device["commands"]["connections"][connection]["tags"]
            if "primary" in tags:
                # This is the primary connection that will be disconnected.
                # Check we know how to disconnect.
                if set(tags) & set(RECOGNIZED_TAGS):
                    primary_connection_has_correct_tags = True
        if not primary_connection_has_correct_tags:
            self.errors = (
                "LAVA does not know how to disconnect: "
                "ensure that primary connection has one of the following tags: {}".format(
                    RECOGNIZED_TAGS
                )
            )

    def run(self, connection, max_end_time):
        connection_namespace = self.parameters.get("connection-namespace")
        parameters = None
        if connection_namespace:
            parameters = {"namespace": connection_namespace}
        else:
            parameters = {"namespace": self.parameters.get("namespace", "common")}
        connection = self.get_namespace_data(
            action="shared",
            label="shared",
            key="connection",
            deepcopy=False,
            parameters=parameters,
        )

        if connection:
            self.logger.debug("Stopping connection")
            connection.disconnect()
            connection.connected = False
            self.set_namespace_data(
                action="shared",
                label="shared",
                key="connection",
                value=None,
                parameters=parameters,
            )
            return None
        else:
            self.logger.debug("Not connected, no need to disconnect.")
        return connection
