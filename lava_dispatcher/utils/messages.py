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

import time
import pexpect
from lava_dispatcher.action import Action
from lava_common.exceptions import TestError, JobError
from lava_common.constants import (
    KERNEL_FREE_UNUSED_MSG,
    KERNEL_FREE_INIT_MSG,
    KERNEL_EXCEPTION_MSG,
    KERNEL_FAULT_MSG,
    KERNEL_PANIC_MSG,
    KERNEL_TRACE_MSG,
    METADATA_MESSAGE_LIMIT,
)
from lava_dispatcher.utils.strings import seconds_to_str
from lava_dispatcher.log import YAMLLogger


class LinuxKernelMessages(Action):
    """
    Adds prompt strings to the boot operation
    to monitor for kernel panics and error strings.
    Previous actions are expected to complete at the
    boot-message and following actions are expected to
    start at the job-specified login prompt.
    Init can generate kernel messages but these cannot
    be tracked by this Action as init has no reliable
    start and end messages. Instead, these are picked
    up by Auto-Login using the get_init_prompts method.
    """

    name = "kernel-messages"
    description = "Test kernel messages during boot."
    summary = "Check for kernel errors, faults and panics."

    EXCEPTION = 0
    FAULT = 1
    PANIC = 2
    TRACE = 3
    # these can be omitted by InitMessages
    FREE_UNUSED = 4
    FREE_INIT = 5

    MESSAGE_CHOICES = (
        (EXCEPTION, KERNEL_EXCEPTION_MSG, 'exception'),
        (FAULT, KERNEL_FAULT_MSG, 'fault'),
        (PANIC, KERNEL_PANIC_MSG, 'panic'),
        (TRACE, KERNEL_TRACE_MSG, 'trace'),
        (FREE_UNUSED, KERNEL_FREE_UNUSED_MSG, 'success'),
        (FREE_INIT, KERNEL_FREE_INIT_MSG, 'success'),
    )

    def __init__(self):
        super().__init__()
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
    def parse_failures(cls, connection, action=None, max_end_time=None):  # pylint: disable=too-many-branches
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
        results = []  # wrap inside a dict to use in results
        res = "pass"
        halt = None
        init = False
        start = time.time()
        if not connection:
            return results
        if cls.MESSAGE_CHOICES[cls.FREE_UNUSED][1] in connection.prompt_str:
            if cls.MESSAGE_CHOICES[cls.FREE_INIT][1] in connection.prompt_str:
                init = True
        remaining = max_end_time - time.time()

        while True:
            if action:
                action.logger.debug(
                    "[%s] Waiting for messages, (timeout %s)",
                    action.name, seconds_to_str(remaining))
            try:
                index = connection.force_prompt_wait(remaining)
            except (pexpect.EOF, pexpect.TIMEOUT, TestError):
                if action:
                    msg = "Failed to match - connection timed out handling messages."
                    action.logger.warning(msg)
                    action.errors = msg
                break

            if action and index:
                action.logger.debug("Matched prompt #%s: %s", index, connection.prompt_str[index])
            message = connection.raw_connection.after
            if index == cls.TRACE or index == cls.EXCEPTION:
                res = "fail"
                if action:
                    action.logger.warning("%s: %s" % (action.name, cls.MESSAGE_CHOICES[index][2]))
                # TRACE may need a newline to force a prompt
                connection.sendline(connection.check_char)
                # this is allowable behaviour, not a failure.
                results.append({
                    cls.MESSAGE_CHOICES[index][2]: cls.MESSAGE_CHOICES[index][1],
                    'message': message[:METADATA_MESSAGE_LIMIT]
                })
                continue
            elif index == cls.PANIC:
                res = "fail"
                if action:
                    action.logger.error("%s %s" % (action.name, cls.MESSAGE_CHOICES[index][2]))
                results.append({
                    cls.MESSAGE_CHOICES[index][2]: cls.MESSAGE_CHOICES[index][1],
                    'message': message[:METADATA_MESSAGE_LIMIT]
                })
                halt = message[:METADATA_MESSAGE_LIMIT]
                break
            elif index and index >= cls.FREE_UNUSED:
                if init and index <= cls.FREE_INIT:
                    results.append({
                        cls.MESSAGE_CHOICES[index][2]: cls.MESSAGE_CHOICES[index][1],
                        'message': 'kernel-messages'
                    })
                    continue
                else:
                    results.append({
                        'success': connection.prompt_str[index]
                    })
                    break
            else:
                break
        # record a specific result for the kernel messages for later debugging.
        if action and isinstance(action.logger, YAMLLogger):
            action.logger.results({  # pylint: disable=no-member
                "definition": "lava",
                "namespace": action.parameters.get('namespace', 'common'),
                "case": cls.name,
                "level": action.level,
                "duration": "%.02f" % (time.time() - start),
                "result": res,
                "extra": {'extra': results}
            })
        if halt:
            # end this job early, kernel is unable to continue
            raise JobError(halt)

        # allow calling actions to also pick up failures
        # without overriding their own success result, if any.
        return results

    def validate(self):
        super().validate()
        if not self.messages:
            self.errors = "Unable to build a list of kernel messages to monitor."

    def run(self, connection, max_end_time):
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
