# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import time

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.shell import ShellCommand, ShellSession
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.strings import substitute
from lava_dispatcher.utils.udev import WaitUSBSerialDeviceAction


class GDB(Boot):
    @classmethod
    def action(cls):
        return BootGDB()

    @classmethod
    def accepts(cls, device, parameters):
        methods = device["actions"]["boot"]["methods"]
        if "gdb" not in methods:
            return False, '"gdb" is not in the device configuration boot methods'
        if parameters["method"] != "gdb":
            return False, '"method" was not "gdb"'
        if "commands" not in parameters:
            return False, '"commands" not in parameters'
        if parameters["commands"] not in methods["gdb"]:
            return (
                False,
                'commands "%s" undefined for the device' % parameters["commands"],
            )

        return True, "accepted"


class BootGDB(Action):
    name = "boot-gdb"
    description = "boot with gdb"
    summary = "boot with gdb"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(BootGDBRetry())


class BootGDBRetry(RetryAction):
    name = "boot-gdb-retry"
    description = "boot with gdb with retry and optional docker support"
    summary = "boot with gdb with retry"

    def __init__(self):
        super().__init__()
        self.gdb = None
        self.gdb_connection = None
        self.commands = []
        self.arguments = []
        self.wait_before_continue = 0
        self.container = None
        self.devices = []

    def validate(self):
        super().validate()
        method = self.job.device["actions"]["boot"]["methods"]["gdb"]
        if "parameters" not in method:
            self.errors = '"parameters" not defined in device configuration'
            return
        if "command" not in method["parameters"]:
            self.errors = (
                '"command" not defined under "parameters" in device configuration'
            )
            return
        self.gdb = method["parameters"]["command"]
        which(self.gdb)

        commands = self.parameters["commands"]
        if commands not in method:
            self.errors = "'%s' not available" % commands
            return
        self.commands = method[commands].get("commands")
        if not isinstance(self.commands, list):
            self.errors = "'commands' should be a list"

        self.arguments = method[commands].get("arguments")
        if not isinstance(self.arguments, list):
            self.errors = "'arguments' should be a list"
        self.wait_before_continue = method["parameters"].get("wait_before_continue", 0)

        # If this is defined, we have to use docker
        if method[commands].get("docker", {}).get("use", False):
            which("docker")
            self.container = method[commands]["docker"].get("container")
            self.container = self.parameters.get("container", self.container)
            if self.container is None:
                self.errors = "a docker container should be defined"
            self.devices = method[commands]["docker"].get("devices", [])
        elif self.parameters.get("container"):
            self.errors = (
                "Requesting a docker container while docker is not used for this device"
            )

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.job.device.hard_reset_command:
            self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(WaitUSBSerialDeviceAction())
        self.pipeline.add_action(ConnectDevice())

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        # Build the substitutions dictionary
        substitutions = {}
        paths = set()
        for action in self.get_namespace_keys("download-action"):
            filename = self.get_namespace_data(
                action="download-action", label=action, key="file"
            )
            if filename is None:
                self.logger.warning(
                    "Empty value for action='download-action' label='%s' key='file'",
                    action,
                )
                continue
            substitutions["{%s}" % action.upper()] = filename
            paths.add(os.path.dirname(filename))

        # If needed, prepend with docker
        if self.container is None:
            cmd = self.gdb
        else:
            cmd = "docker run --rm -it --name lava-%s-%s" % (
                self.job.job_id,
                self.level,
            )
            for path in paths:
                cmd += " --volume %s:%s" % (path, path)
            for device in self.devices:
                cmd += " --device %s:%s:rw" % (device, device)
            cmd += " %s %s" % (self.container, self.gdb)

        for arg in substitute(self.arguments, substitutions):
            cmd += " " + arg

        # Start gdb
        self.logger.info("Starting gdb: %s", cmd)
        shell = ShellCommand(cmd, self.timeout, logger=self.logger)
        gdb = ShellSession(self.job, shell)
        gdb.prompt_str = "\\(gdb\\) "
        self.gdb_connection = gdb
        self.gdb_connection.wait()

        # Send all gdb commands
        for cmd in substitute(self.commands, substitutions):
            self.gdb_connection.sendline(cmd)
            self.gdb_connection.wait()

        # "continue" is send last
        if self.wait_before_continue:
            self.logger.debug(
                "Sleeping %ss before sending 'continue'", self.wait_before_continue
            )
            time.sleep(self.wait_before_continue)
        self.gdb_connection.sendline("continue")

        return connection

    def cleanup(self, connection):
        if self.gdb_connection is None:
            return
        if self.gdb_connection.raw_connection.isalive():
            self.logger.info("Stopping gdb cleanly")
            try:
                self.gdb_connection.wait(max_end_time=time.monotonic() + 1)
                self.gdb_connection.sendline("set confirm no")
                self.gdb_connection.wait(max_end_time=time.monotonic() + 1)
                self.gdb_connection.sendline("quit")
            except JobError:
                self.logger.warning("Unable to quit gdb, killing the process")
            finally:
                # Do not call finalise when using docker or this will kill
                # docker itself and not the underlying gdb.
                if self.container is None:
                    self.gdb_connection.finalise()
                else:
                    name = "lava-%s-%s" % (self.job.job_id, self.level)
                    self.logger.debug("Stopping container %s", name)
                    self.run_command(["docker", "stop", name], allow_fail=True)
