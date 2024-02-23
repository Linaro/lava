# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import os

from lava_common.exceptions import JobError, LAVABug
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.ssh import ConnectSsh
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.shell import which


class SshLogin(Boot):
    """
    Ssh boot strategy is a login process, without actually booting a kernel
    but still needs AutoLoginAction.
    """

    @classmethod
    def action(cls):
        return SshAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "ssh" not in device["actions"]["boot"]["methods"]:
            return False, '"ssh" not in device configuration boot methods'
        if "ssh" not in parameters["method"]:
            return False, '"ssh" not in "method"'
        return True, "accepted"


class SshAction(RetryAction):
    """
    Simple action to wrap AutoLoginAction and ExpectShellSession
    """

    name = "login-ssh"
    description = "connect over ssh and ensure a shell is found"
    summary = "login over ssh"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(Scp("overlay"))
        self.pipeline.add_action(PrepareSsh())
        self.pipeline.add_action(ConnectSsh())
        self.pipeline.add_action(AutoLoginAction(booting=False))
        self.pipeline.add_action(ExpectShellSession())
        self.pipeline.add_action(ExportDeviceEnvironment())
        self.pipeline.add_action(ScpOverlayUnpack())


class Scp(ConnectSsh):
    """
    Use the SSH connection options to copy files over SSH
    One action per scp operation, just as with download action
    Needs the reference into the common data for each file to copy
    This is a Deploy action. lava-start is managed by the protocol,
    when this action starts, the device is in the "receiving" state.
    """

    name = "scp-deploy"
    description = "copy a file to a known device using scp"
    summary = "scp over the ssh connection"

    def __init__(self, key):
        super().__init__()
        self.key = key
        self.scp = []

    def validate(self):
        super().validate()
        params = self._check_params()
        which("scp")
        if "ssh" not in self.job.device["actions"]["deploy"]["methods"]:
            self.errors = "Unable to use %s without ssh deployment" % self.name
        if "ssh" not in self.job.device["actions"]["boot"]["methods"]:
            self.errors = "Unable to use %s without ssh boot" % self.name
        if self.get_namespace_data(
            action="prepare-scp-overlay", label="prepare-scp-overlay", key=self.key
        ):
            self.primary = False
        elif "host" not in self.job.device["actions"]["deploy"]["methods"]["ssh"]:
            self.errors = "Invalid device or job configuration, missing host."
        if (
            not self.primary
            and len(
                self.get_namespace_data(
                    action="prepare-scp-overlay",
                    label="prepare-scp-overlay",
                    key=self.key,
                )
            )
            != 1
        ):
            self.errors = "Invalid number of host_keys"
        if self.primary:
            host_address = self.job.device["actions"]["deploy"]["methods"]["ssh"][
                "host"
            ]
            if not host_address:
                self.errors = (
                    "Unable to retrieve ssh_host address for primary connection."
                )
        if "port" in self.job.device["actions"]["deploy"]["methods"]["ssh"]:
            port = str(self.job.device["actions"]["deploy"]["methods"]["ssh"]["port"])
            if not port.isdigit():
                self.errors = "Port was set but was not a digit"
        if self.valid:
            self.scp.append("scp")
            if "options" in params:
                self.scp.extend(params["options"])

    def run(self, connection, max_end_time):
        path = self.get_namespace_data(
            action="prepare-scp-overlay", label="scp-deploy", key=self.key
        )
        if not path:
            error_msg = "%s: could not find details of '%s'" % (self.name, self.key)
            self.logger.error(error_msg)
            raise JobError(error_msg)

        overrides = self.get_namespace_data(
            action="prepare-scp-overlay", label="prepare-scp-overlay", key=self.key
        )
        if self.primary:
            host_address = self.job.device["actions"]["deploy"]["methods"]["ssh"][
                "host"
            ]
        else:
            self.logger.info(
                "Retrieving common data for prepare-scp-overlay using %s",
                ",".join(overrides),
            )
            host_address = str(
                self.get_namespace_data(
                    action="prepare-scp-overlay",
                    label="prepare-scp-overlay",
                    key=overrides[0],
                )
            )
            self.logger.debug("Using common data for host: %s", host_address)
        if not host_address:
            error_msg = "%s: could not find host for deployment using %s" % (
                self.name,
                self.key,
            )
            self.logger.error(error_msg)
            raise JobError(error_msg)

        lava_test_results_dir = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        destination = os.path.join(lava_test_results_dir, os.path.basename(path))
        command = self.scp[:]  # local copy
        # add the argument for setting the port (-P port)
        command.extend(self.scp_port)
        connection = super().run(connection, max_end_time)
        if self.identity_file:
            command.extend(["-i", self.identity_file])
        # add arguments to ignore host key checking of the host device
        command.extend(
            ["-o", "UserKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=no"]
        )

        self.logger.debug("Create the remote directory %s", lava_test_results_dir)
        connection.sendline("mkdir -p %s" % lava_test_results_dir)
        connection.wait()

        # add the local file as source
        command.append(path)
        command_str = " ".join(str(item) for item in command)
        self.logger.info(
            "Copying %s using %s to %s", self.key, command_str, host_address
        )
        # add the remote as destination, with :/ top level directory
        command.extend(["%s@%s:%s" % (self.ssh_user, host_address, destination)])
        self.run_cmd(command, error_msg="Unable to copy %s" % self.key)
        connection = super().run(connection, max_end_time)
        self.results = {"success": "ssh deployment"}
        self.set_namespace_data(
            action=self.name,
            label="scp-overlay-unpack",
            key="overlay",
            value=destination,
        )
        return connection


class PrepareSsh(Action):
    """
    Sets the host for the ConnectSsh
    """

    name = "prepare-ssh"
    description = "determine which address to use for primary or secondary connections"
    summary = "set the host address of the ssh connection"

    def __init__(self):
        super().__init__()
        self.primary = False

    def validate(self):
        if (
            "parameters" in self.parameters
            and "hostID" in self.parameters["parameters"]
        ):
            self.set_namespace_data(
                action=self.name, label="ssh-connection", key="host", value=True
            )
        else:
            self.set_namespace_data(
                action=self.name, label="ssh-connection", key="host", value=False
            )
            self.primary = True

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not self.primary:
            host_data = self.get_namespace_data(
                action=MultinodeProtocol.name,
                label=MultinodeProtocol.name,
                key=self.parameters["parameters"]["hostID"],
            )
            if not host_data:
                raise JobError(
                    "Unable to retrieve %s - missing ssh deploy?"
                    % self.parameters["parameters"]["hostID"]
                )
            self.set_namespace_data(
                action=self.name,
                label="ssh-connection",
                key="host_address",
                value=host_data[self.parameters["parameters"]["host_key"]],
            )
        return connection


class ScpOverlayUnpack(Action):
    name = "scp-overlay-unpack"
    description = "unpack the overlay over an existing ssh connection"
    summary = "unpack the overlay on the remote device"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not connection:
            raise LAVABug("Cannot unpack, no connection available.")
        filename = self.get_namespace_data(
            action="scp-deploy", label="scp-overlay-unpack", key="overlay"
        )
        tar_flags = self.get_namespace_data(
            action="scp-overlay", label="scp-overlay", key="tar_flags"
        )

        lava_test_results_dir = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )

        cmd = "tar %s -C %s -xzf %s" % (
            tar_flags,
            os.path.dirname(lava_test_results_dir),
            filename,
        )
        connection.sendline(cmd)
        self.wait(connection)
        return connection


class Schroot(Boot):
    @classmethod
    def action(cls):
        return SchrootAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "schroot" not in device["actions"]["boot"]["methods"]:
            return False, '"schroot" was not in the device configuration boot methods'
        if "schroot" not in parameters["method"]:
            return False, '"method" was not "schroot"'
        return True, "accepted"


class SchrootAction(Action):
    """
    Extends the login to enter an existing schroot as a new schroot session
    using the current connection.
    Does not rely on ssh
    """

    name = "schroot-login"
    description = "enter schroot using existing connection"
    summary = "enter specified schroot"

    def __init__(self):
        super().__init__()
        self.schroot = None
        self.command = None

    def validate(self):
        """
        The unit test skips if schroot is not installed, the action marks the
        pipeline as invalid if schroot is not installed.
        """
        if "schroot" not in self.parameters:
            return
        if "schroot" not in self.job.device["actions"]["boot"]["methods"]:
            self.errors = "No schroot support in device boot methods"
            return
        which("schroot")
        # device parameters are for ssh
        params = self.job.device["actions"]["boot"]["methods"]
        if "command" not in params["schroot"]:
            self.errors = "Missing schroot command in device configuration"
            return
        if "name" not in params["schroot"]:
            self.errors = "Missing schroot name in device configuration"
            return
        self.schroot = params["schroot"]["name"]
        self.command = params["schroot"]["command"]

    def run(self, connection, max_end_time):
        if not connection:
            return connection
        self.logger.info("Entering %s schroot", self.schroot)
        connection.prompt_str = "(%s)" % self.schroot
        connection.sendline(self.command)
        self.wait(connection)
        # TODO: not calling super?
        return connection
