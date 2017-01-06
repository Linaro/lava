#
# Copyright (C) 2016 Linaro Limited
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

import pexpect
from lava_dispatcher.pipeline.action import Action
from lava_dispatcher.pipeline.utils.constants import (
    KERNEL_FREE_UNUSED_MSG,
    KERNEL_FREE_INIT_MSG,
    KERNEL_EXCEPTION_MSG,
    KERNEL_FAULT_MSG,
    KERNEL_PANIC_MSG,
    KERNEL_TRACE_MSG,
    KERNEL_INIT_ALERT,
    METADATA_MESSAGE_LIMIT,
)


class LinuxKernelMessages(Action):
    """
    Adds prompt strings to the boot operation
    to monitor for kernel panics and error strings.
    Previous actions are expected to complete at the
    BOOT_MESSAGE and following actions are expected to
    start at the job-specified login prompt.
    Init can generate kernel messages but these cannot
    be tracked by this Action as init has no reliable
    start and end messages. Instead, these are picked
    up by Auto-Login using the get_init_prompts method.
    """

    EXCEPTION = 0
    FAULT = 1
    PANIC = 2
    ALERT = 3
    TRACE = 4
    # these can be omitted by InitMessages
    FREE_UNUSED = 5
    FREE_INIT = 6

    MESSAGE_CHOICES = (
        (EXCEPTION, KERNEL_EXCEPTION_MSG, 'exception'),
        (FAULT, KERNEL_FAULT_MSG, 'fault'),
        (PANIC, KERNEL_PANIC_MSG, 'panic'),
        (TRACE, KERNEL_TRACE_MSG, 'trace'),
        # ALERT is allowable behaviour for some deployments
        # ramdisk just needs a sendline to get to the prompt
        (ALERT, KERNEL_INIT_ALERT, 'alert'),
        (FREE_UNUSED, KERNEL_FREE_UNUSED_MSG, 'success'),
        (FREE_INIT, KERNEL_FREE_INIT_MSG, 'success'),
    )

    def __init__(self):
        super(LinuxKernelMessages, self).__init__()
        self.name = 'kernel-messages'
        self.description = "Test kernel messages during boot."
        self.summary = "Check for kernel errors, faults and panics."
        self.messages = self.get_kernel_prompts()
        self.existing_prompt = None
        for choice in self.MESSAGE_CHOICES:
            self.messages.append(choice[1])

    @classmethod
    def get_kernel_prompts(cls):
        return [prompt[1] for prompt in cls.MESSAGE_CHOICES]

    @classmethod
    def get_init_prompts(cls):
        return [prompt[1] for prompt in cls.MESSAGE_CHOICES[:cls.FREE_UNUSED]]

    @classmethod
    def parse_failures(cls, connection, action=None):  # pylint: disable=too-many-branches
        """
        Returns a list of dictionaries of matches for failure strings and
        other kernel messages.

        If kernel_prompts are in use, a success result is returned containing
        details of which of KERNEL_FREE_UNUSED_MSG and KERNEL_FREE_INIT_MSG
        were parsed. If the returned dictionary only contains this success
        message, then the the kernel-messages action can be deemed as pass.

        The init prompts exclude these messages, so a successful init parse
        returns an empty dictionary as init is generally processed by actions
        which do their own result parsing. If the returned list is not
        empty, add it to the results of the calling action.

        When multiple messages are identified, the list contains one dictionary
        for each message found.

        Always returns a list, the list may be empty.
        """
        results = []
        init = False
        if not connection:
            return results
        if cls.MESSAGE_CHOICES[cls.FREE_UNUSED][1] in connection.prompt_str:
            if cls.MESSAGE_CHOICES[cls.FREE_INIT][1] in connection.prompt_str:
                init = True

        while True:
            try:
                index = connection.wait()
            except (pexpect.EOF, pexpect.TIMEOUT):
                if action:
                    msg = "Failed to match - connection timed out handling messages."
                    action.logger.warning(msg)
                break

            if action and index:
                action.logger.debug("Matched prompt #%s: %s", index, connection.prompt_str[index])
            message = connection.raw_connection.after
            if index == cls.ALERT or index == cls.TRACE:
                if action:
                    action.logger.warning("%s: %s" % (action.name, cls.MESSAGE_CHOICES[index][2]))
                # ALERT or TRACE may need a newline to force a prompt
                connection.sendline(connection.check_char)
                # this is allowable behaviour, not a failure.
                results.append({
                    cls.MESSAGE_CHOICES[index][2]: cls.MESSAGE_CHOICES[index][1],
                    'message': message[:METADATA_MESSAGE_LIMIT]
                })
                continue
            elif index == cls.PANIC or index == cls.EXCEPTION:
                if action:
                    action.logger.error("%s %s" % (action.name, cls.MESSAGE_CHOICES[index][2]))
                results.append({
                    cls.MESSAGE_CHOICES[index][2]: cls.MESSAGE_CHOICES[index][1],
                    'message': message[:METADATA_MESSAGE_LIMIT]
                })
                continue
            elif index and index >= cls.FREE_UNUSED:
                if init and index <= cls.FREE_INIT:
                    results.append({
                        cls.MESSAGE_CHOICES[index][2]: cls.MESSAGE_CHOICES[index][1],
                        'message': 'kernel-messages'
                    })
                    continue
                else:
                    break
            else:
                break
        # allow calling actions to pick up failures
        # without overriding their own success result, if any.
        return results

    def validate(self):
        super(LinuxKernelMessages, self).validate()
        if not self.messages:
            self.errors = "Unable to build a list of kernel messages to monitor."

    def run(self, connection, max_end_time, args=None):
        if not connection:
            return connection
        if not self.existing_prompt:
            self.existing_prompt = connection.prompt_str[:]
            connection.prompt_str = self.get_kernel_prompts()
        if isinstance(self.existing_prompt, list):
            connection.prompt_str.extend(self.existing_prompt)
        else:
            connection.prompt_str.append(self.existing_prompt)
        self.logger.debug(connection.prompt_str)
        results = self.parse_failures(connection)
        if len(results) > 1:
            self.results = {'fail': results}
        elif len(results) == 1:
            self.results = {
                'success': self.name,
                'message': results[0]['message']  # the matching prompt
            }
        else:
            self.results = {'result': 'skipped'}
        return connection
