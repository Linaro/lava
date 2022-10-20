#
# Copyright (C) 2016-2018 Linaro Limited
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

from lava_common.exceptions import TestError, JobError, LAVABug
from lava_common.constants import (
    KERNEL_BUG_MSG,
    KERNEL_FREE_UNUSED_MSG,
    KERNEL_FREE_INIT_MSG,
    KERNEL_EXCEPTION_MSG,
    KERNEL_FAULT_MSG,
    KERNEL_OOPS_MSG,
    KERNEL_PANIC_MSG,
    KERNEL_WARNING_MSG,
    KERNEL_TRACE_MSG,
    METADATA_MESSAGE_LIMIT,
)
from lava_dispatcher.utils.strings import seconds_to_str
from lava_common.log import YAMLLogger


class LinuxKernelMessages:
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
    WARNING = 4
    OOPS = 5
    BUG = 6
    # these can be omitted by InitMessages
    FREE_UNUSED = 7
    FREE_INIT = 8

    MESSAGE_CHOICES = (
        (EXCEPTION, KERNEL_EXCEPTION_MSG, "exception"),
        (FAULT, KERNEL_FAULT_MSG, "fault"),
        (PANIC, KERNEL_PANIC_MSG, "panic"),
        (TRACE, KERNEL_TRACE_MSG, "trace"),
        (WARNING, KERNEL_WARNING_MSG, "warning"),
        (OOPS, KERNEL_OOPS_MSG, "oops"),
        (BUG, KERNEL_BUG_MSG, "bug"),
        (FREE_UNUSED, KERNEL_FREE_UNUSED_MSG, "success"),
        (FREE_INIT, KERNEL_FREE_INIT_MSG, "success"),
    )

    @classmethod
    def get_init_prompts(cls):
        return [prompt[1] for prompt in cls.MESSAGE_CHOICES[: cls.FREE_UNUSED]]

    @classmethod
    def parse_failures(
        cls, connection, action, max_end_time, fail_msg, auto_login=False
    ):
        """
        Returns a list of dictionaries of matches for failure strings and
        other kernel messages.

        If the returned dictionary only contains this success
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
        start = time.monotonic()

        while True:
            remaining = max_end_time - time.monotonic()
            action.logger.debug(
                "[%s] Waiting for messages, (timeout %s)",
                action.name,
                seconds_to_str(remaining),
            )
            try:
                if action.force_prompt:
                    index = connection.force_prompt_wait(remaining)
                else:
                    index = connection.wait(max_end_time)
            except (pexpect.EOF, pexpect.TIMEOUT, TestError):
                msg = "Failed to match - connection timed out handling messages."
                action.logger.warning(msg)
                action.errors = msg
                break

            if index:
                action.logger.debug(
                    "Matched prompt #%s: %s", index, connection.prompt_str[index]
                )
            message = connection.raw_connection.after
            if index in [cls.TRACE, cls.EXCEPTION, cls.WARNING, cls.BUG]:
                res = "fail"
                action.logger.warning(
                    "%s: %s" % (action.name, cls.MESSAGE_CHOICES[index][2])
                )
                # TRACE may need a newline to force a prompt (only when not using auto-login)
                if not auto_login:
                    connection.sendline(connection.check_char)
                # this is allowable behaviour, not a failure.
                results.append(
                    {
                        cls.MESSAGE_CHOICES[index][2]: cls.MESSAGE_CHOICES[index][1],
                        "message": message[:METADATA_MESSAGE_LIMIT],
                    }
                )
                continue
            elif index == cls.PANIC:
                res = "fail"
                action.logger.error(
                    "%s %s" % (action.name, cls.MESSAGE_CHOICES[index][2])
                )
                results.append(
                    {
                        cls.MESSAGE_CHOICES[index][2]: cls.MESSAGE_CHOICES[index][1],
                        "message": message[:METADATA_MESSAGE_LIMIT],
                    }
                )
                halt = message[:METADATA_MESSAGE_LIMIT]
                break
            elif fail_msg and index and fail_msg == connection.prompt_str[index]:
                res = "fail"
                # user has declared this message to be terminal for this test job.
                halt = "Matched job-specific failure message: '%s'" % fail_msg
                action.logger.error("%s %s" % (action.name, halt))
                results.append({"message": "kernel-messages"})
            else:
                break

        # record a specific result for the kernel messages for later debugging.
        if isinstance(action.logger, YAMLLogger):
            action.logger.results(
                {
                    "definition": "lava",
                    "namespace": action.parameters.get("namespace", "common"),
                    "case": cls.name,
                    "level": action.level,
                    "duration": "%.02f" % (time.monotonic() - start),
                    "result": res,
                    "extra": {"extra": results},
                }
            )
        if halt:
            # end this job early, kernel is unable to continue
            raise JobError(halt)

        # allow calling actions to also pick up failures
        # without overriding their own success result, if any.
        return results
