# Copyright (C) 2016 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_common.exceptions import ConfigurationError, InfrastructureError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import BootloaderInterruptAction
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.strings import substitute
from lava_dispatcher.utils.udev import WaitDFUDeviceAction


class DFU(Boot):
    @classmethod
    def action(cls):
        return BootDFURetry()

    @classmethod
    def accepts(cls, device, parameters):
        if "dfu" not in device["actions"]["boot"]["methods"]:
            return False, '"dfu" was not in the device configuration boot methods'
        if parameters["method"] != "dfu":
            return False, '"method" was not "dfu"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class BootDFURetry(RetryAction):
    name = "boot-dfu-retry"
    description = "boot dfu image using the command line interface"
    summary = "boot dfu image"

    def populate(self, parameters):
        dfu = self.job.device["actions"]["boot"]["methods"]["dfu"]
        parameters = dfu["parameters"]

        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ConnectDevice())
        self.pipeline.add_action(ResetDevice())
        if dfu.get("implementation") == "u-boot":
            self.pipeline.add_action(BootloaderInterruptAction(method="u-boot"))
            self.pipeline.add_action(EnterDFU())
        self.pipeline.add_action(WaitDFUDeviceAction())
        self.pipeline.add_action(FlashDFUAction())


class EnterDFU(Action):
    name = "enter-dfu"
    description = "enter software dfu mode"
    summary = "enter software dfu mode"

    def validate(self):
        super().validate()
        parameters = self.job.device["actions"]["boot"]["methods"]["dfu"]["parameters"]
        if "enter-commands" not in parameters:
            self.errors = '"enter-commands" is not defined'
        elif not isinstance(parameters["enter-commands"], list):
            self.errors = '"enter-commands" should be a list'

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        parameters = self.job.device["actions"]["boot"]["methods"]["dfu"]["parameters"]
        for index, cmd in enumerate(parameters["enter-commands"]):
            connection.sendline(cmd)
            # Do not wait for the bootloader prompt for the last command.
            # This command does not return.
            if index + 1 < len(parameters["enter-commands"]):
                connection.wait()


class FlashDFUAction(Action):
    name = "flash-dfu"
    description = "use dfu to flash the images"
    summary = "use dfu to flash the images"

    def __init__(self):
        super().__init__()
        self.base_command = []
        self.exec_list = []
        self.board_id = "0000000000"
        self.usb_vendor_id = "0000"
        self.usb_product_id = "0000"

    def validate(self):
        super().validate()
        try:
            boot = self.job.device["actions"]["boot"]["methods"]["dfu"]
            dfu_binary = which(boot["parameters"]["command"])
            self.base_command = [dfu_binary]
            self.base_command.extend(boot["parameters"].get("options", []))
            if self.job.device["board_id"] == "0000000000":
                self.errors = "[FLASH_DFU] board_id unset"
            if self.job.device["usb_vendor_id"] == "0000":
                self.errors = "[FLASH_DFU] usb_vendor_id unset"
            if self.job.device["usb_product_id"] == "0000":
                self.errors = "[FLASH_DFU] usb_product_id unset"
            self.usb_vendor_id = self.job.device["usb_vendor_id"]
            self.usb_product_id = self.job.device["usb_product_id"]
            self.board_id = self.job.device["board_id"]
            self.base_command.extend(["--serial", self.board_id])
            self.base_command.extend(
                ["--device", "%s:%s" % (self.usb_vendor_id, self.usb_product_id)]
            )
        except AttributeError as exc:
            raise ConfigurationError(exc)
        except (KeyError, TypeError):
            self.errors = "Invalid parameters for %s" % self.name
        substitutions = {}
        for action in self.get_namespace_keys("download-action"):
            dfu_full_command = []
            image_arg = self.get_namespace_data(
                action="download-action", label=action, key="image_arg"
            )
            action_arg = self.get_namespace_data(
                action="download-action", label=action, key="file"
            )
            if not image_arg or not action_arg:
                self.errors = "Missing image_arg for %s. " % action
                continue
            if not isinstance(image_arg, str):
                self.errors = "image_arg is not a string (try quoting it)"
                continue
            substitutions["{%s}" % action] = action_arg
            dfu_full_command.extend(self.base_command)
            dfu_full_command.extend(substitute([image_arg], substitutions))
            self.exec_list.append(dfu_full_command)
        if not self.exec_list:
            self.errors = "No DFU command to execute"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        dfu = self.job.device["actions"]["boot"]["methods"]["dfu"]
        reset_works = dfu.get("reset_works", True)
        implementation = dfu.get("implementation", "hardware")

        # Store the previous prompt_str to restore it afterward
        prompt_str = connection.prompt_str
        if implementation != "hardware":
            connection.prompt_str = self.job.device.get_constant(
                "dfu-download", prefix=implementation
            )

        for index, dfu_command in enumerate(self.exec_list):
            # add --reset for the last command (if reset works)
            if index + 1 == len(self.exec_list) and reset_works:
                dfu_command.extend(["--reset"])
            dfu = " ".join(dfu_command)
            output = self.run_command(dfu.split(" "))
            # Check the output as dfu-util can return 0 in case of errors.
            if output:
                if "No error condition is present\nDone!\n" not in output:
                    raise InfrastructureError("command failed: %s" % dfu)
            else:
                raise InfrastructureError("command failed: %s" % dfu)

            # Wait only for non-hardware implementations
            # In fact, the booloader will print some strings when the transfer
            # is finished.
            if implementation != "hardware":
                connection.wait()

        # Restore the prompts
        connection.prompt_str = prompt_str
        return connection
