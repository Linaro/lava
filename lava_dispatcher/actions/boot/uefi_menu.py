# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from lava_common.constants import (
    DEFAULT_UEFI_LABEL_CLASS,
    LINE_SEPARATOR,
    UEFI_LINE_SEPARATOR,
)
from lava_common.exceptions import InfrastructureError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.menus.menus import (
    MenuConnect,
    MenuInterrupt,
    MenuReset,
    SelectorMenuAction,
)
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.protocols.lxc import LxcProtocol
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.strings import substitute


class UefiMenu(Boot):
    """
    The UEFI Menu strategy selects the specified options
    and inserts relevant strings into the UEFI menu instead
    of issuing commands over a shell-like serial connection.
    """

    @classmethod
    def action(cls):
        return UefiMenuAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "uefi-menu":
            return False, '"method" was not "uefi-menu"'
        if "uefi-menu" in device["actions"]["boot"]["methods"]:
            params = device["actions"]["boot"]["methods"]["uefi-menu"]["parameters"]
            if "interrupt_prompt" in params and "interrupt_string" in params:
                return True, "accepted"
            else:
                return (
                    False,
                    '"interrupt_prompt" or "interrupt_string" was not in the device configuration uefi-menu boot method parameters',
                )
        return False, '"uefi-menu" was not in the device configuration boot methods'


class UEFIMenuInterrupt(MenuInterrupt):
    name = "uefi-menu-interrupt"
    description = "interrupt for uefi menu"
    summary = "interrupt for uefi menu"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.params = None
        self.method = "uefi-menu"

    def validate(self):
        super().validate()
        self.params = self.job.device["actions"]["boot"]["methods"][self.method][
            "parameters"
        ]
        if "interrupt_prompt" not in self.params:
            self.errors = "Missing interrupt prompt"
        if "interrupt_string" not in self.params:
            self.errors = "Missing interrupt string"

    def run(self, connection, max_end_time):
        if not connection:
            self.logger.debug("%s called without active connection", self.name)
            return
        connection = super().run(connection, max_end_time)
        connection.prompt_str = self.params["interrupt_prompt"]
        self.wait(connection)
        connection.raw_connection.send(self.params["interrupt_string"])
        return connection


class UefiMenuSelector(SelectorMenuAction):
    name = "uefi-menu-selector"
    description = "select specified uefi menu items"
    summary = "select options in the uefi menu"

    def __init__(self):
        super().__init__()
        self.selector.prompt = "Start:"
        self.method_name = "uefi-menu"
        self.commands = []
        self.boot_message = None

    def validate(self):
        """
        Setup the items and pattern based on the parameters for this
        specific action, then let the base class complete the validation.
        """
        # pick up the uefi-menu structure
        params = self.job.device["actions"]["boot"]["methods"][self.method_name][
            "parameters"
        ]
        if (
            "item_markup" not in params
            or "item_class" not in params
            or "separator" not in params
        ):
            self.errors = "Missing device parameters for UEFI menu operations"
            return
        if "commands" not in self.parameters and not self.commands:
            self.errors = "Missing commands in action parameters"
            return
        # UEFI menu cannot support command lists (due to renumbering issues)
        # but needs to ignore those which may exist for use with Grub later.
        if not self.commands and isinstance(self.parameters["commands"], str):
            if (
                self.parameters["commands"]
                not in self.job.device["actions"]["boot"]["methods"][self.method_name]
            ):
                self.errors = "Missing commands for %s" % self.parameters["commands"]
                return
            self.commands = self.parameters["commands"]
        if not self.commands:
            # ignore self.parameters['commands'][]
            return
        # pick up the commands for the specific menu
        self.selector.item_markup = params["item_markup"]
        self.selector.item_class = params["item_class"]
        self.selector.separator = params["separator"]
        if "label_class" in params:
            self.selector.label_class = params["label_class"]
        else:
            # label_class is problematic via jinja and yaml templating.
            self.selector.label_class = DEFAULT_UEFI_LABEL_CLASS
        self.selector.prompt = params["bootloader_prompt"]  # initial uefi menu prompt
        if "boot_message" in params and not self.boot_message:
            self.boot_message = params["boot_message"]  # final prompt
        if not self.items:
            # pick up the commands specific to the menu implementation
            if (
                self.commands
                not in self.job.device["actions"]["boot"]["methods"][self.method_name]
            ):
                self.errors = (
                    "No boot configuration called '%s' for boot method '%s'"
                    % (self.commands, self.method_name)
                )
                return
            self.items = self.job.device["actions"]["boot"]["methods"][
                self.method_name
            ][self.commands]
        # set the line separator for the UEFI on this device
        if "line_separator" in self.parameters:
            uefi_type = self.parameters["line_separator"]
        else:
            uefi_type = self.job.device["actions"]["boot"]["methods"][
                self.method_name
            ].get("line_separator", "dos")
        if uefi_type == "dos":
            self.line_sep = UEFI_LINE_SEPARATOR
        elif uefi_type == "unix":
            self.line_sep = LINE_SEPARATOR
        else:
            self.errors = "Unrecognised line separator configuration."
        super().validate()

    def run(self, connection, max_end_time):
        lxc_active = any(
            [
                protocol
                for protocol in self.job.protocols
                if protocol.name == LxcProtocol.name
            ]
        )
        if self.job.device.pre_os_command and not lxc_active:
            self.logger.info("Running pre OS command.")
            command = self.job.device.pre_os_command
            if not self.run_command(command.split(" "), allow_silent=True):
                raise InfrastructureError("%s failed" % command)
        if not connection:
            self.logger.debug("Existing connection in %s", self.name)
            return connection
        connection.prompt_str = self.selector.prompt
        connection.raw_connection.linesep = self.line_sep
        self.logger.debug("Looking for %s", self.selector.prompt)
        self.wait(connection)
        connection = super().run(connection, max_end_time)
        if self.boot_message:
            self.logger.debug("Looking for %s", self.boot_message)
            connection.prompt_str = self.boot_message
            self.wait(connection)
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection


class UefiSubstituteCommands(Action):
    name = "uefi-commands"
    description = "set job-specific variables into the uefi menu commands"
    summary = "substitute job values into uefi commands"

    def __init__(self):
        super().__init__()
        self.items = None

    def validate(self):
        super().validate()
        if (
            self.parameters["commands"]
            not in self.job.device["actions"]["boot"]["methods"]["uefi-menu"]
        ):
            self.errors = "Missing commands for %s" % self.parameters["commands"]
        self.items = self.job.device["actions"]["boot"]["methods"]["uefi-menu"][
            self.parameters["commands"]
        ]
        for item in self.items:
            if "select" not in item:
                self.errors = "Invalid device configuration for %s: %s" % (
                    self.name,
                    item,
                )

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        ip_addr = dispatcher_ip(self.job.parameters["dispatcher"])
        substitution_dictionary = {
            "{SERVER_IP}": ip_addr,
            "{RAMDISK}": self.get_namespace_data(
                action="compress-ramdisk", label="file", key="ramdisk"
            ),
            "{KERNEL}": self.get_namespace_data(
                action="download-action", label="file", key="kernel"
            ),
            "{DTB}": self.get_namespace_data(
                action="download-action", label="file", key="dtb"
            ),
            "TEST_MENU_NAME": "LAVA %s test image" % self.parameters["commands"],
        }
        nfs_address = self.get_namespace_data(
            action="persistent-nfs-overlay", label="nfs_address", key="nfsroot"
        )
        nfs_root = self.get_namespace_data(
            action="download-action", label="file", key="nfsrootfs"
        )
        if nfs_root:
            substitution_dictionary["{NFSROOTFS}"] = self.get_namespace_data(
                action="extract-rootfs", label="file", key="nfsroot"
            )
            substitution_dictionary["{NFS_SERVER_IP}"] = dispatcher_ip(
                self.job.parameters["dispatcher"], "nfs"
            )
        elif nfs_address:
            substitution_dictionary["{NFSROOTFS}"] = nfs_address
            substitution_dictionary["{NFS_SERVER_IP}"] = self.get_namespace_data(
                action="persistent-nfs-overlay", label="nfs_address", key="serverip"
            )
        for item in self.items:
            if "enter" in item["select"]:
                item["select"]["enter"] = substitute(
                    [item["select"]["enter"]], substitution_dictionary
                )[0]
            if "items" in item["select"]:
                # items is already a list, so pass without wrapping in []
                item["select"]["items"] = substitute(
                    item["select"]["items"], substitution_dictionary
                )
        return connection


class UefiMenuAction(RetryAction):
    name = "uefi-menu-action"
    description = "interrupt and select uefi menu items"
    summary = "interact with uefi menu"

    def __init__(self):
        super().__init__()
        self.method = "uefi-menu"

    def validate(self):
        super().validate()
        self.set_namespace_data(
            action=self.name,
            label="bootloader_prompt",
            key="prompt",
            value=self.job.device["actions"]["boot"]["methods"][self.method][
                "parameters"
            ]["bootloader_prompt"],
        )

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if "commands" in parameters and "fastboot" in parameters["commands"]:
            self.pipeline.add_action(UefiSubstituteCommands())
            self.pipeline.add_action(UEFIMenuInterrupt())
            self.pipeline.add_action(UefiMenuSelector())
            self.pipeline.add_action(MenuReset())
            self.pipeline.add_action(AutoLoginAction())
            self.pipeline.add_action(ExportDeviceEnvironment())
        else:
            self.pipeline.add_action(UefiSubstituteCommands())
            self.pipeline.add_action(MenuConnect())
            self.pipeline.add_action(ResetDevice())
            self.pipeline.add_action(UEFIMenuInterrupt())
            self.pipeline.add_action(UefiMenuSelector())
            self.pipeline.add_action(MenuReset())
            self.pipeline.add_action(AutoLoginAction())
            self.pipeline.add_action(ExportDeviceEnvironment())
