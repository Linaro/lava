#
# Copyright (C) 2016-2018 Linaro Limited
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import time

import pexpect

from lava_common.exceptions import JobError, TestError
from lava_common.log import YAMLLogger
from lava_dispatcher.utils.strings import seconds_to_str

# kernel boot monitoring
KERNEL_MESSAGES = [
    {
        "start": r"-\[ cut here \]",
        "end": r"-+\[ end trace \w* \]-+[^\n]*\r",
        "kind": None,
    },
    {
        "start": r"Unhandled fault",
        "end": r"\r",
        "kind": "fault",
    },
    {
        "start": r"BUG: KCSAN:",
        "end": r"=+\r",
        "kind": "kcsan",
    },
    {
        "start": r"BUG: KASAN:",
        "end": r"=+\r",
        "kind": "kasan",
    },
    {
        "start": r"BUG: KFENCE:",
        "end": r"=+\r",
        "kind": "kfence",
    },
    {
        "start": r"Oops(?: -|:)",
        "end": r"\r",
        "kind": "oops",
    },
    {
        "start": r"WARNING:",
        "end": r"end trace[^\r]*\r",
        "kind": "warning",
    },
    {
        "start": r"(kernel BUG at|BUG:)",
        "end": r"\r",
        "kind": "bug",
    },
    {
        "start": r"invalid opcode:",
        "end": r"\r",
        "kind": "invalid opcode",
    },
    {
        "start": r"Kernel panic - not syncing",
        "end": r"end Kernel panic[^\r]*\r",
        "kind": "panic",
        "fatal": True,
    },
]


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

    @classmethod
    def get_init_prompts(cls):
        return [msg["start"] for msg in KERNEL_MESSAGES]

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
        result = "pass"
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
            except (pexpect.EOF, TestError):
                msg = "Failed to match - connection timed out handling messages."
                action.logger.warning(msg)
                action.errors = msg
                break

            if index:
                action.logger.debug(
                    "Matched prompt #%s: %s", index, connection.prompt_str[index]
                )
            message = connection.raw_connection.after
            if index is None:
                break
            if index < len(KERNEL_MESSAGES):
                # Capture the start of the line
                if "\n" in connection.raw_connection.before:
                    start_line = connection.raw_connection.before.rindex("\n")
                    message = (
                        connection.raw_connection.before[start_line + 1 :] + message
                    )
                else:
                    message = connection.raw_connection.before + message

                # Capture the end of the kernel message
                previous_prompts = connection.prompt_str
                connection.prompt_str = [
                    KERNEL_MESSAGES[index]["end"]
                ] + previous_prompts[len(KERNEL_MESSAGES) :]
                try:
                    sub_index = connection.wait(max_end_time, max_searchwindowsize=True)
                except (pexpect.EOF, TestError):
                    msg = "Failed to match end of kernel error"
                    action.logger.warning(msg)
                    action.errors = msg
                    break
                if sub_index != 0:
                    action.logger.warning("Unable to match end of the kernel message")
                    break
                message = (
                    message
                    + connection.raw_connection.before
                    + connection.raw_connection.after[:-1]  # Remove ending "\r"
                )
                connection.prompt_str = previous_prompts

                # Classify the errors
                kind = KERNEL_MESSAGES[index]["kind"]
                if kind is None:
                    if "Oops" in message:
                        kind = "oops"
                    elif "BUG" in message:
                        kind = "bug"
                    elif "WARNING" in message:
                        kind = "warning"
                    else:
                        kind = "unknown"

                if KERNEL_MESSAGES[index].get("fatal"):
                    result = "fail"
                    action.logger.error("%s kernel %r" % (action.name, kind))
                    halt = message
                else:
                    action.logger.warning("%s: kernel %r" % (action.name, kind))

                # TRACE may need a newline to force a prompt (only when not using auto-login)
                if not auto_login and KERNEL_MESSAGES[index]["kind"] == "trace":
                    connection.sendline(connection.check_char)

                results.append(
                    {
                        "kind": kind,
                        "message": message,
                    }
                )
                if KERNEL_MESSAGES[index].get("fatal"):
                    break
                else:
                    continue
            elif fail_msg and index and fail_msg == connection.prompt_str[index]:
                result = "fail"
                # user has declared this message to be terminal for this test job.
                halt = "Matched job-specific failure message: '%s'" % fail_msg
                action.logger.error("%s %s" % (action.name, halt))
                results.append({"message": "kernel-messages"})
                break
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
                    "result": result,
                    "extra": {"extra": results},
                }
            )
        if halt:
            # end this job early, kernel is unable to continue
            raise JobError(halt)

        # allow calling actions to also pick up failures
        # without overriding their own success result, if any.
        return results
