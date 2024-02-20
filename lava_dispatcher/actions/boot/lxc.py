# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import time

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.lxc import ConnectLxc
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.udev import allow_fs_label, get_udev_devices


class BootLxc(Boot):
    """
    Attaches to the lxc container.
    """

    @classmethod
    def action(cls):
        return BootLxcAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "lxc":
            return False, '"method" was not "lxc"'

        return True, "accepted"


class BootLxcAction(RetryAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the
    connection after boot.
    """

    name = "lxc-boot"
    description = "lxc boot into the system"
    summary = "lxc boot"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(LxcStartAction())
        self.pipeline.add_action(LxcAddStaticDevices())
        self.pipeline.add_action(ConnectLxc())
        # Skip AutoLoginAction unconditionally as this action tries to parse kernel message
        # self.pipeline.add_action(AutoLoginAction())
        self.pipeline.add_action(ExpectShellSession())
        self.pipeline.add_action(ExportDeviceEnvironment())


class LxcAddStaticDevices(Action):
    """
    Identifies permanently powered devices which are relevant
    to this LXC and adds the devices to the LXC after startup.
    e.g. Devices providing a tty are often powered from the
    worker.
    """

    name = "lxc-add-static"
    description = "Add devices which are permanently powered by the worker to the LXC"
    summary = "Add static devices to the LXC"

    def get_usb_devices(self):
        """
        Takes static_info from the device, and identifies which
        devices are USB devices. Only passes the USB devices back.
        """
        usb_devices = []
        for device in self.job.device.get("static_info", []):
            if "board_id" in device or "fs_label" in device:
                # This is a USB device
                usb_devices.append(device)
        return usb_devices

    def validate(self):
        super().validate()
        # If there are no USB devices under static_info then this action should be idempotent.

        # If we are allowed to use a filesystem label, we don't require a board_id
        # By default, we do require a board_id (serial)
        requires_board_id = not allow_fs_label(self.job.device)
        try:
            for usb_device in self.get_usb_devices():
                if (
                    usb_device.get("board_id", "") in ["", "0000000000"]
                    and requires_board_id
                ):
                    self.errors = "[LXC_STATIC] board_id unset"
                if usb_device.get("usb_vendor_id", "") == "0000":
                    self.errors = "[LXC_STATIC] usb_vendor_id unset"
                if usb_device.get("usb_product_id", "") == "0000":
                    self.errors = "[LXC_STATIC] usb_product_id unset"
        except TypeError:
            self.errors = "Invalid parameters for %s" % self.name

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        lxc_name = self.get_namespace_data(
            action="lxc-create-action", label="lxc", key="name"
        )
        # If there are no USB devices under static_info then this action should be idempotent.
        if not self.get_usb_devices():
            return connection
        device_list = get_udev_devices(
            job=self.job, logger=self.logger, device_info=self.get_usb_devices()
        )
        for link in device_list:
            lxc_cmd = ["lxc-device", "-n", lxc_name, "add", link]
            cmd_out = self.run_command(lxc_cmd, allow_silent=True)
            if not isinstance(cmd_out, bool) and cmd_out:
                self.logger.debug(cmd_out)
        return connection


class LxcStartAction(Action):
    """
    This action calls lxc-start to get into the system.
    """

    name = "boot-lxc"
    description = "boot into lxc container"
    summary = "attempt to boot"

    def __init__(self):
        super().__init__()
        self.sleep = 10

    def validate(self):
        super().validate()
        which("lxc-start")

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        lxc_name = self.get_namespace_data(
            action="lxc-create-action", label="lxc", key="name"
        )
        lxc_cmd = ["lxc-start", "-n", lxc_name, "-d"]
        command_output = self.run_command(lxc_cmd)
        if command_output and command_output != "":
            raise JobError(
                "Unable to start lxc container: %s" % command_output
            )  # FIXME: JobError needs a unit test
        lxc_cmd = ["lxc-info", "-sH", "-n", lxc_name]
        self.logger.debug("Wait until '%s' state becomes RUNNING", lxc_name)
        while True:
            command_output = self.run_command(lxc_cmd, allow_fail=True)
            if command_output and "RUNNING" in command_output.strip():
                break
            time.sleep(self.sleep)  # poll every 10 seconds.
        self.logger.info("'%s' state is RUNNING", lxc_name)
        # Check if LXC got an IP address so that we are sure, networking is
        # enabled and the LXC can update or install software.
        lxc_cmd = ["lxc-info", "-iH", "-n", lxc_name]
        self.logger.debug("Wait until '%s' gets an IP address", lxc_name)
        while True:
            command_output = self.run_command(lxc_cmd, allow_fail=True)
            if command_output:
                break
            time.sleep(self.sleep)  # poll every 10 seconds.
        self.logger.info("'%s' IP address is: '%s'", lxc_name, command_output.strip())
        return connection


class LxcStopAction(Action):
    """
    This action calls lxc-stop to stop the container.
    """

    name = "lxc-stop"
    description = "stop the lxc container"
    summary = "stop lxc"

    def validate(self):
        super().validate()
        which("lxc-stop")

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        lxc_name = self.get_namespace_data(
            action="lxc-create-action", label="lxc", key="name"
        )
        lxc_cmd = ["lxc-stop", "-k", "-n", lxc_name]
        command_output = self.run_command(lxc_cmd)
        if command_output and command_output != "":
            raise JobError(
                "Unable to stop lxc container: %s" % command_output
            )  # FIXME: JobError needs a unit test
        return connection
