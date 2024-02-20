# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Birch <dean.birch@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_common.constants import UEFI_LINE_SEPARATOR
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import (
    AutoLoginAction,
    BootHasMixin,
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    OverlayUnpack,
)
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.actions.boot.uefi_menu import UEFIMenuInterrupt, UefiMenuSelector
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.menus.menus import MenuConnect, MenuInterrupt
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.shell import ExpectShellSession


class UefiShell(Boot):
    @classmethod
    def action(cls):
        return UefiShellAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "uefi":
            return False, '"method" was not "uefi"'
        if "uefi" in device["actions"]["boot"]["methods"]:
            params = device["actions"]["boot"]["methods"]["uefi"]["parameters"]
            if not params:
                return (
                    False,
                    'there were no parameters in the "uefi" device configuration boot method',
                )
            if "shell_interrupt_string" not in params:
                return (
                    False,
                    '"shell_interrupt_string" was not in the uefi device configuration boot method parameters',
                )
            if "shell_interrupt_prompt" in params and "bootloader_prompt" in params:
                return True, "accepted"
        return (
            False,
            "missing or invalid parameters in the uefi device configuration boot methods",
        )


class UefiShellAction(BootHasMixin, RetryAction):
    name = "uefi-shell-main-action"
    description = "UEFI shell boot action"
    summary = "run UEFI shell to system"

    def __init__(self):
        super().__init__()
        self.shell_menu = []

    def _skip_menu(self, parameters):
        # shell_menu can be set to '' to indicate there is no menu.
        if "shell_menu" in parameters:
            self.shell_menu = parameters["shell_menu"]
        elif (
            "shell_menu"
            in self.job.device["actions"]["boot"]["methods"]["uefi"]["parameters"]
        ):
            self.shell_menu = self.job.device["actions"]["boot"]["methods"]["uefi"][
                "parameters"
            ]["shell_menu"]

        if self.shell_menu and isinstance(self.shell_menu, str):
            return False
        return True

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(BootloaderCommandOverlay())
        self.pipeline.add_action(MenuConnect())
        self.pipeline.add_action(ResetDevice())
        # Newer firmware often needs no menu interaction, just press to drop to shell
        if not self._skip_menu(parameters):
            # Some older firmware, UEFI Shell has to be selected from a menu.
            self.pipeline.add_action(UefiShellMenuInterrupt())
            self.pipeline.add_action(UefiShellMenuSelector())
        self.pipeline.add_action(UefiShellInterrupt())
        self.pipeline.add_action(UefiBootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack())
                self.pipeline.add_action(ExportDeviceEnvironment())

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        connection.raw_connection.linesep = UEFI_LINE_SEPARATOR
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection

    def validate(self):
        super().validate()
        params = self.job.device["actions"]["boot"]["methods"]["uefi"]["parameters"]
        self.set_namespace_data(
            action=self.name,
            label="bootloader_prompt",
            key="prompt",
            value=params["bootloader_prompt"],
        )


class UefiShellMenuInterrupt(UEFIMenuInterrupt):
    name = "uefi-shell-menu-interrupt"
    description = "interrupt default boot and to menu"
    summary = "interrupt default boot and to menu"

    def __init__(self):
        super().__init__()
        # Take parameters from the uefi method, not uefi menu.
        self.method = "uefi"


class UefiBootloaderCommandsAction(BootloaderCommandsAction):
    """
    Same as BootloaderCommandsAction, but uses UEFI_LINE_SEPARATOR.
    """

    def line_separator(self):
        return UEFI_LINE_SEPARATOR


class UefiShellInterrupt(MenuInterrupt):
    """
    Support for interrupting the UEFI menu and dropping to the shell.
    """

    name = "uefi-shell-interrupt"
    description = "interrupt uefi menu to get to a shell"
    summary = "first uefi interrupt"

    def run(self, connection, max_end_time):
        if not connection:
            self.logger.debug("%s called without active connection", self.name)
            return
        connection = super().run(connection, max_end_time)
        # param keys already checked in accepts() classmethod
        params = self.job.device["actions"]["boot"]["methods"]["uefi"]["parameters"]
        connection.prompt_str = params["shell_interrupt_prompt"]
        self.wait(connection)
        connection.raw_connection.send(params["shell_interrupt_string"])
        # now move on to bootloader prompt match
        return connection


class UefiShellMenuSelector(UefiMenuSelector):
    """
    Special version of the UefiMenuSelector configured to drop to the shell
    """

    name = "uefi-shell-menu-selector"
    description = "select uefi menu items to drop to a uefi shell"
    summary = "use uefi menu to drop to shell"

    def __init__(self):
        super().__init__()
        # Take parameters from the uefi method, not uefi menu.
        self.method_name = "uefi"
        # Default menu command name: drop to shell
        self.commands = "shell"

    def validate(self):
        params = self.job.device["actions"]["boot"]["methods"][self.method_name][
            "parameters"
        ]
        if "shell_menu" in self.parameters:
            self.commands = self.parameters["shell_menu"]
        elif "shell_menu" in params:
            self.commands = params["shell_menu"]

        if (
            self.commands
            in self.job.device["actions"]["boot"]["methods"][self.method_name]
        ):
            self.items = self.job.device["actions"]["boot"]["methods"][
                self.method_name
            ][self.commands]
        else:
            self.errors = "Missing menu commands for %s" % self.commands
        if "menu_boot_message" in params:
            self.boot_message = params["menu_boot_message"]
        super().validate()
        if "menu_prompt" in params:
            self.selector.prompt = params["menu_prompt"]
