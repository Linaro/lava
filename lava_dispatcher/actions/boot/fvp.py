# Copyright (C) 2019 Arm Limited
#
# Author: Dean Arnold <dean.arnold@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import re
import shlex
import time
from pathlib import Path

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, BootHasMixin, OverlayUnpack
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ReadFeedback
from lava_dispatcher.shell import ExpectShellSession, ShellCommand, ShellSession


class BootFVP(Boot):
    @classmethod
    def action(cls):
        return BootFVPAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "fvp" not in device["actions"]["boot"]["methods"]:
            return False, '"fvp" was not in the device configuration boot methods'
        if parameters["method"] != "fvp":
            return False, '"method" was not "fvp"'
        if "image" not in parameters:
            return False, '"image" was not in boot parameters'
        return True, "accepted"


class BootFVPAction(BootHasMixin, RetryAction):
    name = "boot-fvp"
    description = "boot fvp"
    summary = "boot fvp"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(BootFVPMain())
        if self.has_prompts(parameters):
            self.pipeline.add_action(ReadFeedback())
            self.pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack())


class BootFVPMain(Action):
    name = "boot-fvp-main"
    description = "boot fvp"
    summary = "boot fvp"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(CheckFVPVersionAction())
        self.pipeline.add_action(StartFVPAction())
        if parameters.get("use_telnet", True):
            self.pipeline.add_action(GetFVPSerialAction())
            self.pipeline.add_action(ReadFeedback())


class BaseFVPAction(Action):
    name = "base-fvp-action"
    description = "call docker run with fvp entry point"
    summary = "base fvp action"

    def __init__(self):
        super().__init__()
        self.extra_options = ""
        self.container = ""
        self.fvp_license = None
        self.ubl_license = None
        self.docker_image = None
        self.local_docker_image = False

    def validate(self):
        super().validate()
        if "docker" not in self.parameters or "name" not in self.parameters.get(
            "docker", {}
        ):
            self.errors = "Specify docker image name"
            raise JobError("Not specified 'docker' in parameters")
        self.docker_image = self.parameters["docker"]["name"]
        self.local_docker_image = self.parameters["docker"].get("local", False)

        # FIXME this emulates the container naming behavior of
        # lava_dispatcher.utils.docker.DockerRun.
        #
        # This entire module should be rewritten to use DockerRun instead of
        # manually composing docker run command lines.
        if "container_name" in self.parameters["docker"]:
            self.container = (
                self.parameters["docker"]["container_name"] + "-lava-" + self.job.job_id
            )
        else:
            self.container = "lava-%s-%s" % (self.job.job_id, self.level)

        options = self.job.device["actions"]["boot"]["methods"]["fvp"]["options"]

        if options["cpus"]:
            self.extra_options += " --cpus %s" % options["cpus"]
        if options["memory"]:
            self.extra_options += " --memory %s" % options["memory"]
        if options.get("privileged", False):
            self.extra_options += " --privileged"
        for device in options.get("devices", []):
            self.extra_options += " --device %s" % device
        for network in options.get("networks", []):
            self.extra_options += " --network %s" % network
        for volume in options.get("volumes", []):
            self.extra_options += " --volume %s" % volume
        if "license_variable" in self.parameters:
            self.fvp_license = shlex.quote(self.parameters["license_variable"])
        if options.get("ubl_license"):
            self.ubl_license = shlex.quote(options["ubl_license"])
        if "ubl_license" in self.parameters:
            self.ubl_license = shlex.quote(self.parameters["ubl_license"])

    def construct_docker_fvp_command(self, docker_image, fvp_arguments):
        substitutions = {}
        cmd = "docker run --rm --interactive --tty --hostname lava"
        cmd += " --name %s" % self.container
        self.logger.debug(
            "Download action namespace keys are: %s",
            self.get_namespace_keys("download-action"),
        )
        for label in self.get_namespace_keys("download-action"):
            filename = self.get_namespace_data(
                action="download-action", label=label, key="file"
            )
            if label == "ramdisk":
                ramdisk = self.get_namespace_data(
                    action="compress-ramdisk", label="file", key="full-path"
                )
                # If overlay has been copied into the ramdisk, use that
                if ramdisk:
                    filename = ramdisk
            if filename is None:
                self.logger.warning(
                    "Empty value for action='download-action' label='%s' key='file'",
                    label,
                )
                continue

            location_in_container = os.path.join(
                "/", self.container, os.path.basename(filename)
            )
            substitutions[label.upper()] = location_in_container

            # Add downloaded images to container, ensuring they are all in a single
            # directory.  This is required for FVP libraries.
            cmd += " --volume %s:%s" % (filename, location_in_container)

        substitutions["ARTIFACT_DIR"] = os.path.join("/", self.container)
        if not self.fvp_license:
            if not self.ubl_license:
                self.logger.warning(
                    "'license_variable' or 'ubl_license' not set, model may not function."
                )
        else:
            cmd += " -e %s" % self.fvp_license
        fvp_image = self.parameters.get("image")
        cmd += self.extra_options

        # Build the script to start the model
        script = Path(self.mkdtemp()) / "script.sh"
        data = "#!/bin/sh\n"

        if self.ubl_license:
            data += f"""
echo "Finding the armlm binary"
ARMLM="$(find /opt/model -maxdepth 1 -type d | grep -v license_terms | tail -n 1)/bin/arm_license_management_utilities/armlm"
if [ -e $ARMLM ]; then
echo "armlm at $ARMLM"
max_retries=5
attempt=0
backoff=1

while [ $attempt -lt $max_retries ]; do
  echo "Trying to Activate UBL license"

  if $ARMLM activate -code {self.ubl_license}; then
    echo "UBL Activation Successful"
    break
  else
    echo "UBL activation failed. Retrying in $backoff seconds..."
    sleep $backoff
    backoff=$((backoff * 2))
    attempt=$((attempt + 1))
  fi
done

if [ $attempt -eq $max_retries ]; then
  echo "UBL Activation failed after $max_retries attempts."
  exit 1
fi

else
echo "No armlm binary found, Won't activate UBL license"
fi
"""
        # Substitute in the fvp arguments
        try:
            fvp_arguments = " \\\n".join(
                line.format(**substitutions) for line in fvp_arguments
            )
        except KeyError as exc:
            raise JobError(f"Key {exc} does not exist, may need escaping")

        self.logger.debug("FVP model arguments:")
        self.logger.debug("%s\n%s", fvp_image, fvp_arguments)

        data += f"""echo "Starting the FVP model"
{fvp_image} {fvp_arguments}"""
        script.write_text(data, encoding="utf-8")

        cmd += f" --volume {script}:/root/script.sh {docker_image} sh /root/script.sh"
        return cmd

    def cleanup(self, connection):
        super().cleanup(connection)
        self.logger.debug(
            "Stopping container %s from action %s", self.container, self.name
        )
        return_value = self.run_cmd(["docker", "stop", self.container], allow_fail=True)
        if return_value == 0:
            self.logger.debug("Stopped container %s", self.container)


class CheckFVPVersionAction(BaseFVPAction):
    name = "check-fvp-version"
    description = "call docker run with fvp version entry point"
    summary = "check fvp version"

    def __init__(self):
        super().__init__()
        self.extra_options = ""
        self.container = ""
        self.fvp_version_string = ""

    def validate(self):
        super().validate()
        self.fvp_version_string = self.parameters.get(
            "version_string", "Fast Models[^\\n]+"
        )

    def run(self, connection, max_end_time):
        start = time.monotonic()

        pull = not self.local_docker_image
        if self.local_docker_image:
            if self.run_cmd(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    f"Image {self.docker_image} exists locally",
                    self.docker_image,
                ],
                allow_fail=True,
            ):
                self.logger.warning(
                    "Unable to inspect docker image '%s'", self.docker_image
                )
                pull = True
        if pull:
            self.logger.debug("Pulling image %s", self.docker_image)
            self.run_cmd(["docker", "pull", self.docker_image])

        fvp_image = self.parameters.get("image")
        fvp_arguments = self.parameters.get("version_args", "--version")

        output = self.parsed_command(
            ["docker", "run", "--rm", self.docker_image, fvp_image, fvp_arguments]
        )
        m = re.match(self.fvp_version_string, output)
        matched_version_string = m and m.group(0) or output
        result = {
            "definition": "lava",
            "case": "fvp-version",
            "level": self.level,
            "extra": {"fvp-version": matched_version_string},
            "result": "pass",
            "duration": "%.02f" % (time.monotonic() - start),
        }
        self.logger.results(result)

        return connection


class StartFVPAction(BaseFVPAction):
    name = "run-fvp"
    description = "call docker run with fvp boot entry point"
    summary = "run fvp model"

    def __init__(self):
        super().__init__()
        self.extra_options = ""
        self.container = ""
        self.fvp_console_string = ""
        self.fvp_feedbacks = set()
        self.fvp_feedback_ports = []
        self.shell = None
        self.shell_session = None

    def validate(self):
        super().validate()
        if "console_string" not in self.parameters:
            self.errors = "'console_string' is not set."
        else:
            self.fvp_console_string = self.parameters.get("console_string")
            self.fvp_feedbacks.add(self.fvp_console_string)
        if "arguments" not in self.parameters:
            self.errors = "'arguments' is not set."
        if "feedbacks" in self.parameters:
            for feedback in self.parameters.get("feedbacks"):
                self.fvp_feedbacks.add(feedback)

    def run(self, connection, max_end_time):
        # Build the command line
        # The docker image is safe to be included in the command line
        cmd = self.construct_docker_fvp_command(
            self.docker_image, self.parameters.get("arguments")
        )
        # Prefix by lava-outerr to add buffering to stdout and err
        cmd = "lava-outerr " + cmd

        self.logger.debug("Boot command: %s", cmd)
        shell = ShellCommand(cmd, self.timeout, logger=self.logger)

        shell_connection = ShellSession(self.job, shell)
        shell_connection = super().run(shell_connection, max_end_time)

        # Wait for the console string
        # shell_connection.prompt_str = self.fvp_console_string
        for str_index in range(len(self.fvp_feedbacks)):
            shell_connection.prompt_str = list(self.fvp_feedbacks)
            self.wait(shell_connection)
            self.logger.debug(
                "Connection group(0) %s"
                % shell_connection.raw_connection.match.group(0)
            )
            if re.match(
                self.fvp_console_string, shell_connection.raw_connection.match.group(0)
            ):
                # this is primary connection
                # We should now have the matched output
                if "PORT" not in shell_connection.raw_connection.match.groupdict():
                    raise JobError(
                        "'console_string' should contain a regular expression section, such as '(?P<PORT>\\d+)' to extract the serial port of the FVP. Group name must be 'PORT'"
                    )

                serial_port = shell_connection.raw_connection.match.groupdict()["PORT"]
                self.set_namespace_data(
                    action=StartFVPAction.name,
                    label="fvp",
                    key="serial_port",
                    value=serial_port,
                )
                self.logger.info("Found FVP port %s", serial_port)
            else:
                serial_port = shell_connection.raw_connection.match.groupdict().get(
                    "PORT", None
                )
                if serial_port:
                    serial_name = shell_connection.raw_connection.match.groupdict().get(
                        "NAME", None
                    )
                    self.fvp_feedback_ports.append(
                        {"port": serial_port, "name": serial_name}
                    )
                    self.logger.info("Found secondary FVP port %s", serial_port)
        self.set_namespace_data(
            action=StartFVPAction.name,
            label="fvp",
            key="feedback_ports",
            value=self.fvp_feedback_ports,
        )
        self.set_namespace_data(
            action=StartFVPAction.name,
            label="fvp",
            key="container",
            value=self.container,
        )
        # Although we don't require any more output on this connection,
        # discarding this may cause SIGHUPs to be sent to the model
        # which will terminate the model.
        self.shell = shell

        self.shell_session = shell_connection
        return shell_connection

    def cleanup(self, connection):
        start = time.monotonic()
        if self.shell_session:
            self.logger.debug("Listening to feedback from FVP binary for 60s.")
            bytes_read = 1
            while bytes_read and (time.monotonic() - start) < 60:
                bytes_read = self.shell_session.listen_feedback(5)
        super().cleanup(connection)
        if self.shell_session:
            self.logger.debug("Listening to feedback from FVP binary.")
            bytes_read = 1
            while bytes_read:
                bytes_read = self.shell_session.listen_feedback(5)


class GetFVPSerialAction(Action):
    name = "fvp-serial-connect"
    description = "connect to the fvp serial connection via telnet"
    summary = "connect to the fvp serial output"

    def run(self, connection, max_end_time):
        serial_port = self.get_namespace_data(
            action=StartFVPAction.name, label="fvp", key="serial_port"
        )
        feedback_ports = self.get_namespace_data(
            action=StartFVPAction.name, label="fvp", key="feedback_ports"
        )
        container = self.get_namespace_data(
            action=StartFVPAction.name, label="fvp", key="container"
        )
        for feedback_dict in feedback_ports:
            cmd = (
                "lava-outerr docker exec --interactive --tty %s telnet localhost %s"
                % (
                    container,
                    feedback_dict["port"],
                )
            )

            self.logger.debug("Feedback command: %s", cmd)
            shell = ShellCommand(cmd, self.timeout, logger=self.logger)

            shell_connection = ShellSession(self.job, shell)
            shell_connection = super().run(shell_connection, max_end_time)
            shell_connection.raw_connection.logfile.is_feedback = True

            feedback_name = feedback_dict.get("name")
            if not feedback_name:
                feedback_name = "_namespace_feedback_%s" % feedback_dict["port"]
            self.set_namespace_data(
                action="shared",
                label="shared",
                key="connection",
                value=shell_connection,
                parameters={"namespace": feedback_name},
            )

        cmd = "lava-outerr docker exec --interactive --tty %s telnet localhost %s" % (
            container,
            serial_port,
        )

        self.logger.debug("Connect command: %s", cmd)
        shell = ShellCommand(cmd, self.timeout, logger=self.logger)

        shell_connection = ShellSession(self.job, shell)
        shell_connection = super().run(shell_connection, max_end_time)

        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=shell_connection
        )
        return shell_connection
