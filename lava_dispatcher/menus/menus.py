# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import re

import pexpect

from lava_common.exceptions import JobError, LAVABug
from lava_dispatcher.action import Action
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.shell import ShellSession


class MovementMenu:
    def __init__(self):
        self.start_pos = 0
        self.label = None
        self.down_command = None


class MenuInterrupt(Action):
    name = "menu-interrupt"
    description = "interrupt the bootloader to start the menu handling"
    summary = "base menu interrupt action"

    def __init__(self):
        super().__init__()
        self.interrupt_prompt = None
        self.interrupt_string = None


class SelectorMenu:
    def __init__(self):
        self.item_markup = None
        self.item_class = None
        self.separator = None
        self.label_class = None
        self.prompt = None  # initial prompt

    @property
    def pattern(self):
        """
        This particular pattern property assumes something like:
        [2] Shell
        where Shell would be the label and 2 the selector to return.
        Derive a new class if you have Shell [2]
        :return: A regex pattern to identify the selector for the matching label.
        """
        return "%s([%s]+)%s%s([%s]*)" % (
            re.escape(self.item_markup[0]),
            self.item_class,
            re.escape(self.item_markup[1]),
            self.separator,
            self.label_class,
        )

    def select(self, output, label):
        output_list = output.split("\n")
        for line in output_list[
            ::-1
        ]:  # start from the end of the list to catch the latest menu first.
            line = line.strip()
            match = re.search(self.pattern, line)
            if match:
                if label == match.group(2):
                    return match.group(1)
        return None


class MenuSession(ShellSession):
    def wait(self, max_end_time=None):
        """
        Simple wait without sendling blank lines as that causes the menu
        to advance without data which can cause blank entries and can cause
        the menu to exit to an unrecognised prompt.
        """
        while True:
            try:
                self.raw_connection.expect(
                    self.prompt_str, timeout=self.timeout.duration
                )
            except pexpect.TIMEOUT:
                raise JobError("wait for prompt timed out")
            else:
                break


class MenuConnect(ConnectDevice):
    """
    Connect actions should not wait for a prompt - ResetDevice needs an active
    connection and the device could be powered off when Connect is called.
    """

    name = "menu-connect"
    description = "change into a menu session"
    summary = "Customise connection for menu operations"

    session_class = MenuSession

    def validate(self):
        if self.job.device.connect_command == "":
            self.errors = "Unable to connect to device"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not connection:
            raise LAVABug("%s needs a Connection")
        connection.check_char = "\n"
        connection.sendline("\n")  # to catch the first prompt (remove for PDU?)
        connection.prompt_str = self.parameters["prompts"]
        if hasattr(
            self.job.device, "power_state"
        ) and self.job.device.power_state not in ["on", "off"]:
            self.wait(connection)
        return connection


class MenuReset(ConnectDevice):
    name = "menu-reset"
    description = "change out of menu session to a shell session"
    summary = "reset to shell connection"

    session_class = ShellSession

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not connection:
            raise LAVABug("%s needs a Connection")

        connection.check_char = "\n"
        connection.sendline("\n")  # to catch the first prompt (remove for PDU?)
        return connection


class SelectorMenuAction(Action):
    name = "menu-selector"
    description = "select specified menu items"
    summary = "select options in a menu"

    def __init__(self):
        super().__init__()
        self.selector = SelectorMenu()
        self.items = []
        self.line_sep = None

    def validate(self):
        super().validate()
        # check for allowed items, error if any are unrecognised
        item_keys = {}
        if not isinstance(self.items, list):
            self.errors = "menu sequence must be a list"
        for item in self.items:
            if "select" in item:
                for _ in item["select"]:
                    item_keys[list(item["select"].keys())[0]] = None
        disallowed = set(item_keys) - {
            "items",
            "prompt",
            "enter",
            "escape",
            "wait",
            "fallback",
        }
        if disallowed:
            self.errors = "Unable to recognise item %s" % disallowed

    def _change_prompt(self, connection, change):
        if change:
            self.logger.debug("Changing menu prompt to '%s'", connection.prompt_str)
            connection.wait()  # call MenuSession::wait directly for a tighter loop

    def run(self, connection, max_end_time):
        """
        iterate through the menu sequence:
        items: select
        prompt: prompt_str
        enter: <str> & Ctrl-M
        escape: Ctrl-[ through pexpect.sendcontrol

        :param menu: list of menus
        :param connection: Connection to use to interact with the menu
        :param logger: Action logger
        :return: connection
        """
        connection = super().run(connection, max_end_time)
        if not connection:
            self.logger.error("%s called without a Connection", self.name)
            return connection
        for block in self.items:
            if "select" in block:
                change_prompt = False
                # ensure the prompt is changed just before sending the action to allow it to be matched.
                if "wait" in block["select"]:
                    connection.prompt_str = block["select"]["wait"]
                    change_prompt = True
                if "items" in block["select"]:
                    for selector in block["select"]["items"]:
                        menu_text = connection.raw_connection.before
                        action = self.selector.select(menu_text, selector)
                        if action:
                            self.logger.debug("Selecting option %s", action)
                        elif "fallback" in block["select"]:
                            action = self.selector.select(
                                menu_text, block["select"]["fallback"]
                            )
                        if not action:
                            raise JobError("No selection was made")
                        connection.sendline(action, delay=self.character_delay)
                        self._change_prompt(connection, change_prompt)
                if "escape" in block["select"]:
                    self.logger.debug("Sending escape")
                    connection.raw_connection.sendcontrol("[")
                    self._change_prompt(connection, change_prompt)
                if "enter" in block["select"]:
                    self.logger.debug("Sending %s Ctrl-M", block["select"]["enter"])
                    connection.raw_connection.send(
                        block["select"]["enter"], delay=self.character_delay
                    )
                    connection.raw_connection.sendcontrol("M")
                    self._change_prompt(connection, change_prompt)
            else:
                raise JobError("Unable to recognise selection %s" % block["select"])
        return connection


class DebianInstallerMenu(MovementMenu):
    def __init__(self):
        super().__init__()
        self.down_command = "[1B"
