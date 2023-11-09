# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import os
import re
import shutil
import subprocess  # nosec - internal
import traceback

import yaml

from lava_common.constants import (
    LAVA_LXC_TIMEOUT,
    LXC_PATH,
    LXC_PROTOCOL,
    UDEV_RULES_DIR,
)
from lava_common.exceptions import InfrastructureError, JobError, LAVABug, TestError
from lava_common.timeout import Timeout
from lava_dispatcher.connection import Protocol
from lava_dispatcher.utils.filesystem import lxc_path


class LxcProtocol(Protocol):
    """
    Lxc API protocol.
    """

    name = LXC_PROTOCOL

    def __init__(self, parameters, job_id):
        super().__init__(parameters, job_id)
        self.system_timeout = Timeout("system", None, duration=LAVA_LXC_TIMEOUT)
        self.persistence = parameters["protocols"][self.name].get("persist", False)
        if self.persistence:
            self.lxc_name = parameters["protocols"][self.name]["name"]
        else:
            self.lxc_name = "-".join(
                [parameters["protocols"][self.name]["name"], str(job_id)]
            )
        self.lxc_dist = parameters["protocols"][self.name]["distribution"]
        self.lxc_release = parameters["protocols"][self.name]["release"]
        self.lxc_arch = parameters["protocols"][self.name].get("arch")
        self.lxc_template = parameters["protocols"][self.name].get(
            "template", "download"
        )
        self.lxc_mirror = parameters["protocols"][self.name].get("mirror", None)
        self.lxc_security_mirror = parameters["protocols"][self.name].get(
            "security_mirror"
        )
        self.verbose = parameters["protocols"][self.name].get("verbose", False)
        self.fastboot_reboot = parameters.get("reboot_to_fastboot", True)
        self.custom_lxc_path = False
        if LXC_PATH != lxc_path(parameters["dispatcher"]):
            self.custom_lxc_path = True
        self.logger = logging.getLogger("dispatcher")
        self.job_prefix = parameters["dispatcher"].get("prefix", "")

    @classmethod
    def accepts(cls, parameters):
        if "protocols" not in parameters:
            return False
        if "lava-lxc" not in parameters["protocols"]:
            return False
        if "name" not in parameters["protocols"]["lava-lxc"]:
            return False
        if "distribution" not in parameters["protocols"]["lava-lxc"]:
            return False
        if "release" not in parameters["protocols"]["lava-lxc"]:
            return False
        return True

    def set_up(self):
        """
        Called from the job at the start of the run step.
        """
        pass

    def _api_select(self, data, action=None):
        if not data:
            raise TestError("[%s] Protocol called without any data." % self.name)
        if not action:
            raise LAVABug("LXC protocol needs to be called from an action.")
        for item in data:
            if "request" not in item:
                raise LAVABug("[%s] Malformed protocol request data." % self.name)
            if "pre-os-command" in item["request"]:
                action.logger.info(
                    "[%s] Running pre OS command via protocol.", self.name
                )
                command = action.job.device.pre_os_command
                if not command:
                    raise JobError("No pre OS command is defined for this device.")
                if not isinstance(command, list):
                    command = [command]
                for cmd in command:
                    if not action.run_command(cmd.split(" "), allow_silent=True):
                        raise InfrastructureError("%s failed" % cmd)
                continue
            elif "pre-power-command" in item["request"]:
                action.logger.info(
                    "[%s] Running pre-power-command via protocol.", self.name
                )
                command = action.job.device.pre_power_command
                if not command:
                    raise JobError("No pre power command is defined for this device.")

                if not isinstance(command, list):
                    command = [command]
                for cmd in command:
                    if not action.run_command(cmd.split(" "), allow_silent=True):
                        raise InfrastructureError("%s failed" % cmd)
                continue
            else:
                raise JobError(
                    "[%s] Unrecognised protocol request: %s" % (self.name, item)
                )

    def __call__(self, *args, **kwargs):
        action = kwargs.get("action")
        logger = action.logger if action else logging.getLogger("dispatcher")
        self.logger.debug("[%s] Checking protocol data for %s", action.name, self.name)
        try:
            return self._api_select(args, action=action)
        except yaml.YAMLError as exc:
            msg = re.sub(r"\s+", " ", "".join(traceback.format_exc().split("\n")))
            logger.exception(msg)
            raise JobError("Invalid call to %s %s" % (self.name, exc))

    def _call_handler(self, command):
        try:
            self.logger.debug("%s protocol: executing '%s'", self.name, command)
            output = subprocess.check_output(  # nosec - internal
                command.split(" "), stderr=subprocess.STDOUT
            )
            if output:
                self.logger.debug(output)
        except subprocess.CalledProcessError:
            self.logger.debug("%s protocol: FAILED executing '%s'", self.name, command)

    def finalise_protocol(self, device=None):
        """Called by Finalize action to power down and clean up the assigned
        device.
        """
        # Reboot devices to bootloader if required, based on the availability
        # of adb_serial_number.
        # Do not reboot to bootloader if 'reboot_to_fastboot' is set to
        # 'false' in job definition.
        if self.fastboot_reboot:
            if "adb_serial_number" in device:
                reboot_cmd = "lxc-attach -n {} -- adb reboot bootloader".format(
                    self.lxc_name
                )
                self._call_handler(reboot_cmd)
        else:
            self.logger.info("%s protocol: device not rebooting to fastboot", self.name)

        # Stop the container.
        self.logger.debug("%s protocol: issue stop", self.name)
        stop_cmd = f"lxc-stop -n {self.lxc_name} -k"
        self._call_handler(stop_cmd)
        # Check if the container should persist and skip destroying it.
        if self.persistence:
            self.logger.debug("%s protocol: persistence requested", self.name)
        else:
            self.logger.debug("%s protocol: issue destroy", self.name)
            if self.custom_lxc_path:
                abs_path = os.path.realpath(os.path.join(LXC_PATH, self.lxc_name))
                destroy_cmd = "lxc-destroy -n {} -f -P {}".format(
                    self.lxc_name, os.path.dirname(abs_path)
                )
            else:
                destroy_cmd = f"lxc-destroy -n {self.lxc_name} -f"
            self._call_handler(destroy_cmd)

            dirname = os.path.join(LXC_PATH, self.lxc_name)
            self.logger.debug("%s protocol: removing %s", self.name, dirname)
            shutil.rmtree(dirname, ignore_errors=True)

        # Remove udev rule which added device to the container and then reload
        # udev rules.
        rules_file_name = "100-lava-" + self.job_prefix + self.lxc_name + ".rules"
        rules_file = os.path.join(UDEV_RULES_DIR, rules_file_name)
        if os.path.exists(rules_file):
            os.remove(rules_file)
            self.logger.debug(
                "%s protocol: removed udev rules '%s'", self.name, rules_file
            )
        reload_cmd = "udevadm control --reload-rules"
        self._call_handler(reload_cmd)
        self.logger.debug("%s protocol finalised.", self.name)
