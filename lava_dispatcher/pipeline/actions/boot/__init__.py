# Copyright (C) 2014 Linaro Limited
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

import pyudev
from lava_dispatcher.pipeline.action import (
    Action,
    InfrastructureError
)
from lava_dispatcher.pipeline.logical import RetryAction
from lava_dispatcher.pipeline.utils.constants import (
    AUTOLOGIN_DEFAULT_TIMEOUT,
    DEFAULT_SHELL_PROMPT,
    DISTINCTIVE_PROMPT_CHARACTERS,
    LINE_SEPARATOR,
)
from lava_dispatcher.pipeline.utils.shell import wait_for_prompt
from lava_dispatcher.pipeline.utils.messages import LinuxKernelMessages


class BootAction(RetryAction):
    """
    Base class for all actions which control power-on
    and boot behaviour of a device under test.
    The subclass selected to do the work will be the
    subclass returning True in the accepts(device_type, image)
    function.
    Each new subclass needs a unit test to ensure it is
    reliably selected for the correct job and not
    selected for an invalid job or a job
    accepted by a different subclass.

    Boot and Test are closely related - a fail error in Boot
    will cause subsequent Test actions to be skipped.
    """

    name = 'boot'

    def has_prompts(self, parameters):
        return ('prompts' in parameters)

    def has_boot_finished(self, parameters):
        return ('boot_finished' in parameters)


class AutoLoginAction(Action):
    """
    Automatically login on the device.
    If 'auto_login' is not present in the parameters, this action does nothing.

    This Action expect POSIX-compatible support of PS1 from shell
    """
    def __init__(self):
        super(AutoLoginAction, self).__init__()
        self.name = 'auto-login-action'
        self.description = "automatically login after boot using job parameters and checking for messages."
        self.summary = "Auto-login after boot with support for kernel messages."
        self.check_prompt_characters_warning = (
            "The string '%s' does not look like a typical prompt and"
            " could match status messages instead. Please check the"
            " job log files and use a prompt string which matches the"
            " actual prompt string more closely."
        )

    def validate(self):  # pylint: disable=too-many-branches
        super(AutoLoginAction, self).validate()
        # Skip auto login if the configuration is not found
        params = self.parameters.get('auto_login', None)
        if params:
            if not isinstance(params, dict):
                self.errors = "'auto_login' should be a dictionary"
                return

            if 'login_prompt' not in params:
                self.errors = "'login_prompt' is mandatory for auto_login"
            if not params['login_prompt']:
                self.errors = "Value for 'login_prompt' cannot be empty"
            if 'username' not in params:
                self.errors = "'username' is mandatory for auto_login"

            if 'password_prompt' in params:
                if 'password' not in params:
                    self.errors = "'password' is mandatory if 'password_prompt' is used in auto_login"

        prompts = self.parameters.get('prompts', None)
        if prompts is None:
            self.errors = "'prompts' is mandatory for AutoLoginAction"

        if not isinstance(prompts, (list, str)):
            self.errors = "'prompts' should be a list or a str"

        if not prompts:
            self.errors = "Value for 'prompts' cannot be empty"

        if isinstance(prompts, list):
            for prompt in prompts:
                if not prompt:
                    self.errors = "Items of 'prompts' can't be empty"

    def check_kernel_messages(self, connection):
        """
        Use the additional pexpect expressions to detect warnings
        and errors during the kernel boot. Ensure all test jobs using
        auto-login-action have a result set so that the duration is
        always available when the action completes successfully.
        """
        self.logger.info("Parsing kernel messages")
        self.logger.debug(connection.prompt_str)
        parsed = LinuxKernelMessages.parse_failures(connection, self)
        if len(parsed) and 'success' in parsed[0]:
            self.results = {'success': parsed[0]}
        elif not parsed:
            self.results = {'success': "No kernel warnings or errors detected."}
        else:
            self.results = {'fail': parsed}
            self.logger.warning("Kernel warnings or errors detected.")

    def run(self, connection, args=None):
        # Prompts commonly include # - when logging such strings,
        # use lazy logging or the string will not be quoted correctly.
        def check_prompt_characters(chk_prompt):
            if not any([True for c in DISTINCTIVE_PROMPT_CHARACTERS if c in chk_prompt]):
                self.logger.warning(self.check_prompt_characters_warning, chk_prompt)

        prompts = self.parameters.get('prompts', None)
        for prompt in prompts:
            check_prompt_characters(prompt)

        connection.prompt_str = LinuxKernelMessages.get_init_prompts()
        connection.prompt_str.extend(prompts)
        # linesep should come from deployment_data as from now on it is OS dependent
        linesep = self.get_namespace_data(
            action='deploy-device-env',
            label='environment',
            key='line_separator'
        )
        connection.raw_connection.linesep = linesep if linesep else LINE_SEPARATOR
        self.logger.debug("Using line separator: #%r#", connection.raw_connection.linesep)

        # Skip auto login if the configuration is not found
        params = self.parameters.get('auto_login', None)
        if not params:
            self.logger.debug("Skipping of auto login")
            # wait for a prompt or kernel messages
            self.check_kernel_messages(connection)
            # clear kernel message prompt patterns
            connection.prompt_str = self.parameters.get('prompts', [])
            # already matched one of the prompts
        else:
            self.logger.info("Waiting for the login prompt")
            connection.prompt_str.append(params['login_prompt'])

            # wait for a prompt or kernel messages
            self.check_kernel_messages(connection)
            self.logger.debug("Sending username %s", params['username'])
            connection.sendline(params['username'], delay=self.character_delay)
            # clear the kernel_messages patterns
            connection.prompt_str = self.parameters.get('prompts', [])

            if 'password_prompt' in params:
                self.logger.info("Waiting for password prompt")
                connection.prompt_str.append(params['password_prompt'])
                # wait for the password prompt
                index = self.wait(connection)
                if index:
                    self.logger.debug("Matched prompt #%s: %s", index, connection.prompt_str[index])
                self.logger.debug("Sending password %s", params['password'])
                connection.sendline(params['password'], delay=self.character_delay)
                # clear the Password pattern
                connection.prompt_str = self.parameters.get('prompts', [])

            # wait for the login process to provide the prompt
            index = self.wait(connection)
            if index:
                self.logger.debug("Matched %s %s", index, connection.prompt_str[index])

        connection.prompt_str.extend([DEFAULT_SHELL_PROMPT])
        self.logger.debug("Setting shell prompt(s) to %s" % connection.prompt_str)  # pylint: disable=logging-not-lazy
        connection.sendline('export PS1="%s"' % DEFAULT_SHELL_PROMPT, delay=self.character_delay)

        return connection


class WaitUSBDeviceAction(Action):

    def __init__(self):
        super(WaitUSBDeviceAction, self).__init__()
        self.name = "wait-usb-device"
        self.description = "wait for udev to see USB device"
        self.summary = self.description
        self.board_id = '0000000000'
        self.usb_vendor_id = '0000'
        self.usb_product_id = '0000'

    def validate(self):
        super(WaitUSBDeviceAction, self).validate()
        try:
            self.usb_vendor_id = self.job.device['usb_vendor_id']
            self.usb_product_id = self.job.device['usb_product_id']
            self.board_id = self.job.device['board_id']
        except AttributeError as exc:
            raise InfrastructureError(exc)
        except (KeyError, TypeError):
            self.errors = "Invalid parameters for %s" % self.name
        if self.job.device['board_id'] == '0000000000':
            self.errors = "board_id unset"
        if self.job.device['usb_vendor_id'] == '0000':
            self.errors = 'usb_vendor_id unset'
        if self.job.device['usb_product_id'] == '0000':
            self.errors = 'usb_product_id unset'

    def run(self, connection, args=None):
        self.logger.info("Waiting for USB device... %s:%s %s", self.usb_vendor_id, self.usb_product_id, self.board_id)
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by('usb', 'usb_device')
        for device in iter(monitor.poll, None):
            if (device.get('ID_SERIAL_SHORT', '') == str(self.board_id)) \
               and (device.get('ID_VENDOR_ID', '') == str(self.usb_vendor_id)) \
               and (device.get('ID_MODEL_ID', '') == str(self.usb_product_id)):
                break
        return connection
