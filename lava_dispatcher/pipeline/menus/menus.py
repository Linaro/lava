# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import re
import pexpect
from lava_dispatcher.pipeline.shell import ShellSession
from lava_dispatcher.pipeline.action import Action, JobError
from lava_dispatcher.pipeline.connections.serial import ConnectDevice

# pylint: disable=too-few-public-methods,too-many-branches


class MovementMenu(object):

    def __init__(self):
        self.start_pos = 0
        self.label = None
        self.down_command = None


class MenuInterrupt(Action):

    def __init__(self):
        super(MenuInterrupt, self).__init__()
        self.name = "menu-interrupt"
        self.summary = "base menu interrupt action"
        self.description = "interrupt the bootloader to start the menu handling"
        self.interrupt_prompt = None
        self.interrupt_string = None


class SelectorMenu(object):

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
            self.label_class
        )

    def select(self, output, label):
        output_list = output.split('\n')
        for line in output_list[::-1]:  # start from the end of the list to catch the latest menu first.
            line = line.strip()
            match = re.search(self.pattern, line)
            if match:
                if label == match.group(2):
                    return match.group(1)
        return None


class MenuSession(ShellSession):

    def wait(self):
        """
        Simple wait without sendling blank lines as that causes the menu
        to advance without data which can cause blank entries and can cause
        the menu to exit to an unrecognised prompt.
        """
        while True:
            try:
                self.raw_connection.expect(self.prompt_str, timeout=self.timeout.duration)
            except pexpect.TIMEOUT:
                raise JobError("wait for prompt timed out")
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            else:
                break


class MenuConnect(ConnectDevice):
    """
    Connect actions should not wait for a prompt - ResetDevice needs an active
    connection and the device could be powered off when Connect is called.
    """

    def __init__(self):
        super(MenuConnect, self).__init__()
        self.session_class = MenuSession
        self.name = "menu-connect"
        self.summary = "Customise connection for menu operations"
        self.description = "change into a menu session"

    def validate(self):
        hostname = self.job.device['hostname']
        if self.job.device.power_state in ['on', 'off']:
            # to enable power to a device, either power_on or hard_reset are needed.
            if self.job.device.power_command is '':
                self.errors = "Unable to power on or reset the device %s" % hostname
            if self.job.device.connect_command is '':
                self.errors = "Unable to connect to device %s" % hostname
        else:
            self.logger.warning("%s may need manual intervention to reboot", hostname)

    def run(self, connection, args=None):
        connection = super(MenuConnect, self).run(connection, args)
        if not connection:
            raise RuntimeError("%s needs a Connection")
        connection.check_char = '\n'
        connection.sendline('\n')  # to catch the first prompt (remove for PDU?)
        connection.prompt_str = self.parameters['prompts']
        if self.job.device.power_state not in ['on', 'off']:
            self.wait(connection)
        return connection


class MenuReset(ConnectDevice):

    def __init__(self):
        super(MenuReset, self).__init__()
        self.session_class = ShellSession
        self.name = "menu-reset"
        self.summary = "reset to shell connection"
        self.description = "change out of menu session to a shell session"

    def run(self, connection, args=None):
        connection = super(MenuReset, self).run(connection, args)
        if not connection:
            raise RuntimeError("%s needs a Connection")

        connection.check_char = '\n'
        connection.sendline('\n')  # to catch the first prompt (remove for PDU?)
        return connection


class SelectorMenuAction(Action):

    def __init__(self):
        super(SelectorMenuAction, self).__init__()
        self.name = 'menu-selector'
        self.summary = 'select options in a menu'
        self.description = 'select specified menu items'
        self.selector = SelectorMenu()
        self.items = []
        self.send_char_delay = 0

    def validate(self):
        super(SelectorMenuAction, self).validate()
        # check for allowed items, error if any are unrecognised
        item_keys = {}
        if not isinstance(self.items, list):
            self.errors = "menu sequence must be a list"
        for item in self.items:
            if 'select' in item:
                for _ in item['select']:
                    item_keys[list(item['select'].keys())[0]] = None
        disallowed = set(item_keys) - {'items', 'prompt', 'enter', 'escape', 'wait', 'fallback'}
        if disallowed:
            self.errors = "Unable to recognise item %s" % disallowed

    def _change_prompt(self, connection, change):
        if change:
            self.logger.debug("Changing menu prompt to '%s'", connection.prompt_str)
            connection.wait()  # call MenuSession::wait directly for a tighter loop

    def run(self, connection, args=None):
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
        if not connection:
            self.logger.error("%s called without a Connection", self.name)
            return connection
        for block in self.items:
            if 'select' in block:
                change_prompt = False
                # ensure the prompt is changed just before sending the action to allow it to be matched.
                if 'wait' in block['select']:
                    connection.prompt_str = block['select']['wait']
                    change_prompt = True
                if 'items' in block['select']:
                    for selector in block['select']['items']:
                        menu_text = connection.raw_connection.before
                        action = self.selector.select(menu_text, selector)
                        if action:
                            self.logger.debug("Selecting option %s", action)
                        elif 'fallback' in block['select']:
                            action = self.selector.select(menu_text, block['select']['fallback'])
                        connection.sendline(action)
                        self._change_prompt(connection, change_prompt)
                if 'escape' in block['select']:
                    self.logger.debug("Sending escape")
                    connection.raw_connection.sendcontrol('[')
                    self._change_prompt(connection, change_prompt)
                if 'enter' in block['select']:
                    self.logger.debug("Sending %s Ctrl-M", block['select']['enter'])
                    connection.raw_connection.send(block['select']['enter'], delay=self.send_char_delay)
                    connection.raw_connection.sendcontrol('M')
                    self._change_prompt(connection, change_prompt)
            else:
                raise JobError("Unable to recognise selection %s" % block['select'])
        return connection


class DebianInstallerMenu(MovementMenu):

    def __init__(self):
        super(DebianInstallerMenu, self).__init__()
        self.down_command = '[1B'
