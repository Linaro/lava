# Copyright (C) 2016 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import shutil
import time

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.filesystem import mkdtemp
from lava_dispatcher.utils.udev import WaitDevicePathAction, WaitUSBSerialDeviceAction


class CMSIS(Boot):
    @classmethod
    def action(cls):
        return BootCMSISRetry()

    @classmethod
    def accepts(cls, device, parameters):
        if "cmsis-dap" not in device["actions"]["boot"]["methods"]:
            return False, '"cmsis-dap" is not in the device configuration boot methods'
        if parameters["method"] != "cmsis-dap":
            return False, '"method" was not "cmsis-dap"'
        if "board_id" not in device:
            return False, 'device has no "board_id" configured'
        if "parameters" not in device["actions"]["boot"]["methods"]["cmsis-dap"]:
            return (
                False,
                '"parameters" was not in the device boot method configuration for "cmsis-dap"',
            )
        if (
            "usb_mass_device"
            not in device["actions"]["boot"]["methods"]["cmsis-dap"]["parameters"]
        ):
            return (
                False,
                '"usb_mass_device" was not in the device configuration "cmsis-dap" boot method parameters',
            )
        return True, "accepted"


class BootCMSISRetry(RetryAction):
    name = "boot-cmsis-retry"
    description = "boot cmsis usb image with retry"
    summary = "boot cmsis usb image with retry"

    def validate(self):
        super().validate()
        method_params = self.job.device["actions"]["boot"]["methods"]["cmsis-dap"][
            "parameters"
        ]
        usb_mass_device = method_params.get("usb_mass_device")
        if not usb_mass_device:
            self.errors = "usb_mass_device unset"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        method_params = self.job.device["actions"]["boot"]["methods"]["cmsis-dap"][
            "parameters"
        ]
        usb_mass_device = method_params.get("usb_mass_device")
        resets_after_flash = method_params.get("resets_after_flash", True)
        if self.job.device.hard_reset_command:
            self.pipeline.add_action(ResetDevice())
            self.pipeline.add_action(WaitDevicePathAction(usb_mass_device))
        self.pipeline.add_action(FlashCMSISAction())
        if resets_after_flash:
            self.pipeline.add_action(WaitUSBSerialDeviceAction())
        self.pipeline.add_action(ConnectDevice())


class FlashCMSISAction(Action):
    name = "flash-cmsis"
    description = "flash cmsis to usb mass storage"
    summary = "flash cmsis to usb mass storage"
    command_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.filelist = []
        self.usb_mass_device = None

    def validate(self):
        super().validate()
        if self.job.device["board_id"] == "0000000000":
            self.errors = "[FLASH_CMSIS] board_id unset"
        method_parameters = self.job.device["actions"]["boot"]["methods"]["cmsis-dap"][
            "parameters"
        ]
        self.usb_mass_device = method_parameters.get("usb_mass_device")
        if not self.usb_mass_device:
            self.errors = "usb_mass_device unset"
        for action in self.get_namespace_keys("download-action"):
            action_arg = self.get_namespace_data(
                action="download-action", label=action, key="file"
            )
            self.filelist.extend([action_arg])

    def _sync_data(self, dstdir, method_parameters):
        """Make sure that data was actually written (programmed) to the
        underlying device and detect any errors with that."""

        # Waiting for CMSIS_DAP auto remount is the default behavior,
        # but we allow to bypass it in case that particular hardware
        # has problems with it.
        if method_parameters.get("skip_autoremount_wait", False):
            self.run_cmd(["sync", dstdir], error_msg="Unable to sync %s" % dstdir)
        else:
            t_start = time.monotonic()
            self.logger.debug("Waiting for CMSIS-DAP MSD to self-unmount")
            while True:
                # os.sync() causes OS to pick up changes on the underlying MSD device.
                os.sync()
                if not os.listdir(dstdir):
                    break
                # Small delay so we didn't miss this "unmount".
                time.sleep(0.1)

            self.logger.debug("Waiting for CMSIS-DAP MSD to self-remount")
            while True:
                # os.sync() causes OS to pick up changes on the underlying MSD device.
                os.sync()
                flist = os.listdir(dstdir)
                if flist:
                    break
                time.sleep(0.5)

            self.logger.debug(
                "CMSIS-DAP MSD self-remount cycle: %.2fs" % (time.monotonic() - t_start)
            )

            if "FAIL.TXT" in flist:
                with open(dstdir + "/FAIL.TXT") as f:
                    fail_txt = f.read().rstrip()
                raise InfrastructureError(
                    "Unsuccessful cmsis-dap boot: FAIL.TXT present after file copying: "
                    + fail_txt
                )

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        method_parameters = self.job.device["actions"]["boot"]["methods"]["cmsis-dap"][
            "parameters"
        ]
        dstdir = mkdtemp()
        # mount
        self.run_cmd(
            ["mount", "-t", "vfat", self.usb_mass_device, dstdir],
            error_msg="Unable to mount USB device %s" % self.usb_mass_device,
        )
        # log DAPLink metadata, to be able to correlate possible job issues
        # with bootloader version/options
        self.logger.debug("DAPLink virtual disk files: %s" % os.listdir(dstdir))
        if os.path.isfile(dstdir + "/DETAILS.TXT"):
            with open(dstdir + "/DETAILS.TXT") as f:
                self.logger.debug(
                    "DAPLink Firmware DETAILS.TXT:\n%s" % f.read().replace("\r\n", "\n")
                )

        try:
            # copy files
            for f in self.filelist:
                self.logger.debug("Copying %s to %s", f, dstdir)
                shutil.copy2(f, dstdir)
            # sync written data
            self._sync_data(dstdir, method_parameters)
        finally:
            # umount
            self.run_cmd(
                ["umount", self.usb_mass_device],
                error_msg="Unable to unmount USB device %s" % self.usb_mass_device,
            )

        post_unmount_delay = method_parameters.get("post_unmount_delay", 1)
        self.logger.debug("Post-unmount stabilization delay: %ss" % post_unmount_delay)
        time.sleep(post_unmount_delay)

        return connection
