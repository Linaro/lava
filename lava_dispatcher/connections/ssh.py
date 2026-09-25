# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.exceptions import InfrastructureError, JobError, LAVABug
from lava_dispatcher.action import Action
from lava_dispatcher.shell import ShellSession
from lava_dispatcher.utils.filesystem import check_ssh_identity_file
from lava_dispatcher.utils.shell import which

if TYPE_CHECKING:
    from typing import Any

    from lava_dispatcher.job import Job


class SShSession(ShellSession):
    """Extends a ShellSession to include the ability to copy files using scp
    without duplicating the SSH setup, keys etc.
    """

    name = "SshSession"

    def finalise(self) -> None:
        self.disconnect("closing")
        super().finalise()

    def disconnect(self, reason: str = "") -> None:
        # FIXME: handle super if tags are present.
        self.sendline("logout", disconnecting=True)
        self.connected = False


class ConnectSsh(Action):
    """
    Initiate an SSH connection from the dispatcher to a device.
    Connections from test images can be done in test definitions.
    If hostID and host_key are not specified as parameters,
    this class reads the destination data directly from the device configuration.
    This is a Boot action with Retry support.

    Note the syntax requirements of methods:
    methods:
    -  image
    -  ssh:

    This allows ssh to be a dict, image to be a string (or a dict) and methods to be a list.
    """

    name = "ssh-connection"
    description = "login to a known device using ssh"
    summary = "make an ssh connection to a device"
    timeout_exception = InfrastructureError

    def __init__(self, job: Job):
        super().__init__(job)
        self.command: list[str] | None = None
        self.host: str | None = None
        self.ssh_port: list[str] = ["-p", "22"]
        self.scp_port: list[str] = ["-P", "22"]
        self.identity_file: str | None = None
        self.ssh_user = "root"
        self.primary = False
        self.scp_prompt: str | None = None

    def _check_params(self) -> dict[str, Any] | None:
        # the deployment strategy ensures that this key exists
        # use a different class if the destination is set using common_data, e.g. protocols
        if not any(
            "ssh" in data for data in self.job.device["actions"]["deploy"]["methods"]
        ):
            self.errors_add(
                "Invalid device configuration - no suitable deploy method for ssh"
            )
            return None
        params: dict[str, dict[str, Any]] = self.job.device["actions"]["deploy"][
            "methods"
        ]
        if "identity_file" in self.job.device["actions"]["deploy"]["methods"]["ssh"]:
            check = check_ssh_identity_file(params)
            if check[0]:
                self.errors_add(check[0])
            elif check[1]:
                self.identity_file = check[1]
        if "ssh" not in params:
            self.errors_add(
                "Empty ssh parameter list in device configuration %s" % params
            )
            return None
        if "options" in params["ssh"]:
            if any(
                option
                for option in params["ssh"]["options"]
                if not isinstance(option, str)
            ):
                msg = [
                    (option, type(option))
                    for option in params["ssh"]["options"]
                    if not isinstance(option, str)
                ]
                self.errors_add(
                    "[%s] Invalid device configuration: all options must be only strings: %s"
                    % (self.name, msg)
                )
                return None
        if "port" in params["ssh"]:
            self.ssh_port = ["-p", "%s" % str(params["ssh"]["port"])]
            self.scp_port = ["-P", "%s" % str(params["ssh"]["port"])]
        if "host" in params["ssh"] and params["ssh"]["host"]:
            # get the value from the protocol later.
            self.host = params["ssh"]["host"]
        if "user" in params["ssh"] and params["ssh"]["user"]:
            self.ssh_user = params["ssh"]["user"]
        return params["ssh"]

    def validate(self) -> None:
        super().validate()
        params = self._check_params()
        which("ssh")
        if "serial" not in self.job.device["actions"]["boot"]["connections"]:
            self.errors_add("Device not configured to support serial connection.")
        if "host" in self.job.device["actions"]["deploy"]["methods"]["ssh"]:
            self.primary = True
            self.host = self.job.device["actions"]["deploy"]["methods"]["ssh"]["host"]
        if params is None:
            # Validation failed in `self._check_params`
            return
        if self.valid:
            self.command = ["ssh"]
            if "options" in params:
                self.command.extend(params["options"])
            # add arguments to ignore host key checking of the host device
            self.command.extend(
                ["-o", "UserKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=no"]
            )
            if self.identity_file:
                # add optional identity file
                self.command.extend(["-i", self.identity_file])
            self.command.extend(self.ssh_port)

    def run(
        self, connection: ShellSession | None, max_end_time: float | None
    ) -> ShellSession | None:
        existing_ssh_connection: ShellSession | None = self.get_namespace_data(
            action="shared", label="shared", key="connection", deepcopy=False
        )
        if existing_ssh_connection:
            self.logger.debug("Already connected")
            return existing_ssh_connection
        # ShellSession executes the connection command and monitors the pexpect

        self._check_params()
        if self.command is None:
            raise LAVABug("SSH command list not initialised")
        command = self.command[:]  # local copy for idempotency
        overrides: list[str] | None = self.get_namespace_data(
            action="prepare-scp-overlay", label="prepare-scp-overlay", key="overlay"
        )
        host_address: str | None = None
        if overrides:
            host_address = str(
                self.get_namespace_data(
                    action="prepare-scp-overlay",
                    label="prepare-scp-overlay",
                    key=overrides[0],
                )
            )
        if host_address:
            self.logger.info(
                "Using common data to retrieve host_address for secondary connection."
            )
            command_str = " ".join(str(item) for item in command)
            self.logger.info(
                "%s Connecting to device %s@%s using '%s'",
                self.name,
                self.ssh_user,
                host_address,
                command_str,
            )
            command.append(f"{self.ssh_user}@{host_address}")
        elif self.host and self.primary:
            self.logger.info("Using device data host_address for primary connection.")
            command_str = " ".join(str(item) for item in command)
            self.logger.info(
                "%s Connecting to device %s@%s using '%s'",
                self.name,
                self.ssh_user,
                self.host,
                command_str,
            )
            command.append(f"{self.ssh_user}@{self.host}")
        else:
            raise JobError(
                "Unable to identify host address. Primary? %s" % self.primary
            )
        command_str = " ".join(str(item) for item in command)
        # SshSession monitors the pexpect
        new_ssh_connection = SShSession(
            f"{command_str}\n", self.timeout, logger=self.logger
        )
        existing_ssh_connection = super().run(new_ssh_connection, max_end_time)
        if existing_ssh_connection is not None:
            existing_ssh_connection.prompt_str = list(
                self.parameters.get("prompts", [])
            )
            existing_ssh_connection.connected = True
        self.wait(connection)
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection
