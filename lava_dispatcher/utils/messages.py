#
# Copyright (C) 2016-2018 Linaro Limited
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from enum import auto as enum_auto
from re import compile as re_compile
from typing import TYPE_CHECKING

import pexpect

from lava_common.exceptions import JobError, TestError
from lava_common.log import YAMLLogger
from lava_dispatcher.utils.strings import seconds_to_str

if TYPE_CHECKING:
    from re import Pattern
    from typing import TypedDict

    from ..action import Action
    from ..shell import ShellSession

    class ParsingResult(TypedDict):
        message: str
        kind: str


class KernelMessageKind(Enum):
    NONE = enum_auto()
    TRACE = enum_auto()
    FAULT = enum_auto()
    KCSAN = enum_auto()
    KASAN = enum_auto()
    KFENCE = enum_auto()
    WARNING = enum_auto()
    BUG = enum_auto()
    OOPS = enum_auto()
    INVALID_OPCODE = enum_auto()
    PANIC = enum_auto()
    RESET = enum_auto()


class KernelMessageType(Enum):
    SINGLE_LINE = enum_auto()
    MULTILINE_START = enum_auto()
    MULTILINE_END = enum_auto()
    MULTILINE_END_OR_SINGLE = enum_auto()
    SINGLE_OR_MULTILINE_MOD = enum_auto()


@dataclass(frozen=True)
class KernelMessage:
    pattern: Pattern[str]
    kind: KernelMessageKind
    fatal: bool = False
    type: KernelMessageType = KernelMessageType.SINGLE_LINE
    timeout_msg: str | None = None


TRACE_START = KernelMessage(
    pattern=re_compile(r"-\[ cut here \]-"),
    kind=KernelMessageKind.TRACE,
    type=KernelMessageType.MULTILINE_START,
)
TRACE_END = KernelMessage(
    pattern=re_compile(r"-\[ end trace .*"),
    kind=KernelMessageKind.TRACE,
    type=KernelMessageType.MULTILINE_END,
)
UNHANDLED_FAULT = KernelMessage(
    pattern=re_compile(r"Unhandled fault.*"),
    kind=KernelMessageKind.FAULT,
)
BUG_KCSAN = KernelMessage(
    pattern=re_compile(r"BUG: KCSAN:.*"),
    kind=KernelMessageKind.KCSAN,
    type=KernelMessageType.MULTILINE_START,
)
BUG_KASAN = KernelMessage(
    pattern=re_compile(r"BUG: KASAN:.*"),
    kind=KernelMessageKind.KASAN,
    type=KernelMessageType.MULTILINE_START,
)
BUG_KFENCE = KernelMessage(
    pattern=re_compile(r"BUG: KFENCE:.*"),
    kind=KernelMessageKind.KFENCE,
    type=KernelMessageType.MULTILINE_START,
)
KSAN_TERM = KernelMessage(  # KCSAN, KASAN, KFENCE termination
    pattern=re_compile(r"={5,}"),
    kind=KernelMessageKind.KFENCE,
    type=KernelMessageType.MULTILINE_END,
)
KERNEL_OOPS = KernelMessage(
    pattern=re_compile(r"Oops(?: -|:).*"),
    kind=KernelMessageKind.OOPS,
    type=KernelMessageType.SINGLE_OR_MULTILINE_MOD,
)
WARNING = KernelMessage(
    pattern=re_compile(r"WARNING:"),
    kind=KernelMessageKind.WARNING,
    type=KernelMessageType.SINGLE_OR_MULTILINE_MOD,
)
BUG = KernelMessage(
    pattern=re_compile(r"(kernel BUG at|BUG:).*"),
    kind=KernelMessageKind.BUG,
    type=KernelMessageType.SINGLE_OR_MULTILINE_MOD,
)
PANIC_START = KernelMessage(
    pattern=re_compile(r"Kernel panic - not syncing"),
    kind=KernelMessageKind.PANIC,
    type=KernelMessageType.MULTILINE_START,
    timeout_msg="Kernel panic - not syncing",
)
PANIC_END = KernelMessage(
    pattern=re_compile(r"---\[ end Kernel panic - not syncing.*"),
    kind=KernelMessageKind.PANIC,
    fatal=True,
    type=KernelMessageType.MULTILINE_END,
)
UBOOT_RESET = KernelMessage(
    pattern=re_compile(r"U-Boot SPL 20[0-9][0-9].*"),
    kind=KernelMessageKind.RESET,
    fatal=True,
)

MULTILINE_MAP: dict[KernelMessage, KernelMessage] = {
    TRACE_START: TRACE_END,
    BUG_KCSAN: KSAN_TERM,
    BUG_KASAN: KSAN_TERM,
    BUG_KFENCE: KSAN_TERM,
    PANIC_START: PANIC_END,
}

KERNEL_MESSAGES_FLAT: list[KernelMessage] = [
    TRACE_START,
    TRACE_END,
    UNHANDLED_FAULT,
    BUG_KCSAN,
    BUG_KASAN,
    BUG_KFENCE,
    KSAN_TERM,
    KERNEL_OOPS,
    WARNING,
    BUG,
    PANIC_START,
    PANIC_END,
    UBOOT_RESET,
]


def string_before_new_line(s: str) -> str:
    return s[s.rfind("\n") + 1 :]


class KernelMessageFactory:
    def __init__(self, results: list[ParsingResult], connection: ShellSession) -> None:
        self.results = results
        self.connection = connection
        self.fatal = False

        self.current_message = ""
        self.current_kind: KernelMessageKind = KernelMessageKind.NONE
        self.current_multiline_end: KernelMessage | None = None
        self.current_timeout_msg: str | None = None

        self.last_message = ""
        self.last_kind: KernelMessageKind = KernelMessageKind.NONE

    def process_message(self, message: KernelMessage) -> None:
        message_after = self.connection.raw_connection.after
        if not isinstance(message_after, str):
            message_after = ""
        message_before = self.connection.raw_connection.before
        if not isinstance(message_before, str):
            message_before = ""

        # Set fatal once and don't clear it
        self.fatal = self.fatal | message.fatal

        if message.type == KernelMessageType.SINGLE_LINE:
            if self.current_kind.value > message.kind.value:
                # Skip if current priority higher than message
                self.current_message += message_before + message_after
            else:
                self.message_flush()
                self.current_message = (
                    string_before_new_line(message_before) + message_after
                )
                self.current_kind = message.kind
                self.message_flush()
        elif message.type == KernelMessageType.MULTILINE_START:
            if self.current_kind.value >= message.kind.value:
                # Skip if current priority higher or equal than current message
                self.current_message += message_before + message_after
            else:
                self.current_message += (
                    string_before_new_line(message_before) + message_after
                )
                self.current_kind = message.kind
                self.current_multiline_end = MULTILINE_MAP[message]
                self.current_timeout_msg = message.timeout_msg
        elif message.type == KernelMessageType.MULTILINE_END:
            # If message end encountered without accumulated text
            # simply ignore it.
            if not self.current_message:
                return

            self.current_message += message_before + message_after
            if (
                message.kind.value >= self.current_kind.value
                or self.current_multiline_end == message
            ):
                # Flush multiline message if priority is equal or larger
                # or matching end is found.
                self.message_flush()
        elif message.type == KernelMessageType.SINGLE_OR_MULTILINE_MOD:
            if self.current_kind.value > message.kind.value:
                self.current_message += message_before + message_after
            else:
                if self.current_message:
                    self.current_kind = message.kind
                    self.current_message += message_before + message_after
                else:
                    self.message_flush()
                    self.current_message = (
                        string_before_new_line(message_before) + message_after
                    )
                    self.current_kind = message.kind
                    self.message_flush()
        else:
            raise ValueError(f"Unknown kernel message type: {message!r}")

    def message_flush(self) -> None:
        if self.current_message:
            self.results.append(
                {
                    "kind": self.current_kind.name.lower().replace("_", " "),
                    "message": self.current_message.removesuffix("\r"),
                }
            )

        self.last_message = self.current_message
        self.last_kind = self.current_kind

        self.current_message = ""
        self.current_kind = KernelMessageKind.NONE
        self.current_multiline_end = None
        self.current_timeout_msg = None


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
    def get_init_prompts(cls) -> list[Pattern[str]]:
        return [msg.pattern for msg in KERNEL_MESSAGES_FLAT]

    @classmethod
    def parse_failures(
        cls,
        connection: ShellSession,
        action: Action,
        max_end_time: float,
        fail_msg: str,
        auto_login: bool = False,
    ) -> list[ParsingResult]:
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
        results: list[ParsingResult] = []  # wrap inside a dict to use in results
        result = "pass"
        halt: str | None = None
        start = time.monotonic()

        message_factory = KernelMessageFactory(results, connection)

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
                    index = connection.wait(
                        max_end_time,
                        job_error_message=message_factory.current_timeout_msg,
                    )
            except (pexpect.EOF, TestError):
                msg = "Failed to match - connection timed out handling messages."
                action.logger.warning(msg)
                action.errors = msg
                break

            if index < len(KERNEL_MESSAGES_FLAT):
                matched_kernel_message = KERNEL_MESSAGES_FLAT[index]
                message_factory.process_message(matched_kernel_message)

                if message_factory.fatal:
                    result = "fail"
                    action.logger.error(
                        "%s kernel %r", action.name, message_factory.last_kind
                    )
                    halt = message_factory.last_message
                else:
                    action.logger.warning(
                        "%s: kernel %r", action.name, message_factory.last_kind
                    )

                if message_factory.fatal:
                    break
                else:
                    continue
            elif fail_msg and index and fail_msg == connection.prompt_str[index]:
                result = "fail"
                # user has declared this message to be terminal for this test job.
                halt = "Matched job-specific failure message: '%s'" % fail_msg
                action.logger.error("%s %s" % (action.name, halt))
                results.append({"message": "kernel-messages", "kind": "fail"})
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
