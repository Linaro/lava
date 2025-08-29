# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import contextlib
import logging
import time
from os import killpg as os_killpg
from re import Match
from re import error as re_error
from re import split as re_split
from signal import SIGKILL
from typing import TYPE_CHECKING, overload

import pexpect

from lava_common.constants import LINE_SEPARATOR
from lava_common.exceptions import (
    ConnectionClosedError,
    InfrastructureError,
    JobError,
    LAVABug,
    TestError,
)
from lava_common.timeout import Timeout
from lava_dispatcher.action import Action
from lava_dispatcher.utils.strings import seconds_to_str

if TYPE_CHECKING:
    from collections.abc import Awaitable, Iterator
    from re import Pattern
    from typing import Literal

    from pexpect import EOF, TIMEOUT

    from lava_common.log import YAMLLogger
    from lava_dispatcher.job import Job

    SpawnBase = pexpect.spawn[str]
else:
    # Workaround for real pexpect.spawn not being generic
    # but typeshed hints being generic
    SpawnBase = pexpect.spawn


class ShellLogger:
    """
    Builds a YAML log message out of the incremental output of the pexpect.spawn
    using the logfile support built into pexpect.
    """

    def __init__(self, logger: YAMLLogger, is_input: bool = False):
        self.line = ""
        self.logger = logger
        self.is_feedback = False
        self.is_input = is_input
        self.namespace: str | None = None

    def write(self, new_line: str) -> None:
        replacements = {"\x1b": ""}  # remove escape control characters
        lines = self.line + new_line

        # Print one full line at a time. A partial line is kept in memory.
        if "\n" in lines:
            last_ret = lines.rindex("\n")
            self.line = lines[last_ret + 1 :]
            lines = lines[: last_ret + 1]
            for line in re_split("\r\r\n|\r\n|\n", lines)[:-1]:
                for key, value in replacements.items():
                    line = line.replace(key, value)
                if self.is_feedback:
                    if self.namespace:
                        self.logger.feedback(line, namespace=self.namespace)
                    else:
                        self.logger.feedback(line)
                elif self.is_input:
                    self.logger.input(line)
                else:
                    self.logger.target(line)
        else:
            self.line = lines
        return

    def flush(self, force: bool = False) -> None:
        if force and self.line:
            self.write("\n")


class ShellCommand(SpawnBase):
    """
    Run a command over a connection using pexpect instead of
    subprocess, i.e. not on the dispatcher itself.
    Takes a Timeout object (to support overrides and logging)

    https://pexpect.readthedocs.io/en/stable/api/pexpect.html#spawn-class

    Window size is managed to limit impact on performance.
    maxread is left at default to ensure the entire log is captured.

    A ShellCommand is a raw_connection for a ShellConnection instance.
    """

    def __init__(
        self,
        command: str,
        lava_timeout: Timeout,
        logger: YAMLLogger | None = None,
        cwd: str | None = None,
        window: int = 2000,
    ):
        if isinstance(window, str):
            # constants need to be stored as strings.
            try:
                window = int(window)
            except ValueError:
                raise LAVABug(
                    "ShellCommand was passed an invalid window size of %s bytes."
                    % window
                )
        searchwindowsize = 2 * window
        if not lava_timeout or not isinstance(lava_timeout, Timeout):
            raise LAVABug("ShellCommand needs a timeout set by the calling Action")
        if not logger:
            raise LAVABug("ShellCommand needs a logger")
        super().__init__(
            command,
            timeout=lava_timeout.duration,
            cwd=cwd,
            logfile=None,  # Split logging
            encoding="utf-8",
            # Data before searchwindowsize point is preserved, but not searched.
            searchwindowsize=searchwindowsize,  # pattern match in twice the window size
            maxread=window,  # limit the size of the buffer. 1 to turn off buffering
            codec_errors="replace",
        )
        # logfile_read and logfile_send can be None.
        # Create new variables that cannot be None.
        self.output_logger = ShellLogger(logger)
        self.logfile_read = self.output_logger
        self.input_logger = ShellLogger(logger, is_input=True)
        self.logfile_send = self.input_logger
        self.name = "ShellCommand"
        self.logger = logger
        # delayafterterminate allow for some spare time for a process to terminate
        # If the system is loaded
        # See https://github.com/pexpect/pexpect/issues/462
        self.delayafterterminate = 1.0
        self.delaybeforesend = None  # LAVA implements its own delay between characters.
        # lava-run is single threaded, there is no concern about GIL not being released
        # between read calls. Remove delay after read.
        # Typeshed type hints has incorrectly marked `delayafterread` as float only.
        self.delayafterread = None  # type: ignore[assignment]
        # set a default newline character, but allow actions to override as necessary
        self.linesep = LINE_SEPARATOR
        self.lava_timeout = lava_timeout

    def sendline(  # type: ignore[override]
        self, s: str = "", delay: float = 0.0
    ) -> int:
        """
        Extends pexpect.sendline so that it can support the delay argument which allows a delay
        between sending each character to get around slow serial problems (iPXE).
        pexpect sendline does exactly the same thing: calls send for the string then os.linesep.

        :param s: string to send
        :param delay: delay in milliseconds between sending each character
        """
        send_char = False
        if delay > 0:
            self.logger.debug("Sending with %s millisecond of delay", delay)
            send_char = True
        self.logger.debug("Sending line: %r", s)
        self.send(s, delay, send_char)
        return self.send(self.linesep, delay)

    def sendcontrol(self, char: str) -> int:
        self.logger.debug("Sending character: %r", char)
        return super().sendcontrol(char)

    def send(  # type: ignore[override]
        self, string: str, delay: float = 0.0, send_char: bool = True
    ) -> int:
        """
        Extends pexpect.send to support extra arguments, delay and send by character flags.
        """
        sent = 0
        if not string:
            return sent
        delay = float(delay) / 1000
        if send_char:
            # If string is bytes send one byte at a time.
            # When iterating over bytes int gets yielded so convert it to a bytes
            # with length of 1.
            for char in string:
                sent += super().send(char)
                time.sleep(delay)
        else:
            sent = super().send(string)
        return sent

    # Copy pasted overloads from super class method
    @overload
    def expect(
        self,
        pattern: (
            Pattern[str]
            | Pattern[bytes]
            | str
            | bytes
            | type[EOF]
            | type[TIMEOUT]
            | list[
                Pattern[str] | Pattern[bytes] | str | bytes | type[EOF] | type[TIMEOUT]
            ]
        ),
        timeout: float | None = -1,
        searchwindowsize: int | None = None,
        async_: Literal[False] = False,
    ) -> int:
        ...

    @overload
    def expect(
        self,
        pattern: (
            Pattern[str]
            | Pattern[bytes]
            | str
            | bytes
            | type[EOF]
            | type[TIMEOUT]
            | list[
                Pattern[str] | Pattern[bytes] | str | bytes | type[EOF] | type[TIMEOUT]
            ]
        ),
        timeout: float | None = -1,
        searchwindowsize: int | None = None,
        async_: Literal[True] = True,
    ) -> Awaitable[int]:
        ...

    def expect(
        self,
        pattern: (
            Pattern[str]
            | Pattern[bytes]
            | str
            | bytes
            | type[EOF]
            | type[TIMEOUT]
            | list[
                Pattern[str] | Pattern[bytes] | str | bytes | type[EOF] | type[TIMEOUT]
            ]
        ),
        timeout: float | None = -1,
        searchwindowsize: int | None = None,
        async_: Literal[True] | Literal[False] = False,
    ) -> int | Awaitable[int]:
        """
        No point doing explicit logging here, the SignalDirector can help
        the TestShellAction make much more useful reports of what was matched
        """
        try:
            proc = super().expect(
                pattern=pattern,
                timeout=timeout,
                searchwindowsize=searchwindowsize,
                async_=async_,
            )
        except re_error as exc:
            msg = f"Invalid regular expression {exc.pattern!r}: {exc.msg}"
            raise TestError(msg)
        except pexpect.TIMEOUT:
            raise TestError("ShellCommand command timed out.")
        except ValueError as exc:
            raise TestError(exc)
        except pexpect.EOF:
            # FIXME: deliberately closing the connection (and starting a new one) needs to be supported.
            raise ConnectionClosedError("Connection closed")
        return proc

    def flush(self) -> None:
        """Will be called by pexpect itself when closing the connection"""
        self.input_logger.flush(force=True)
        self.output_logger.flush(force=True)


class ShellSession:
    name = "ShellSession"

    def __init__(self, shell_command: ShellCommand):
        """
        A ShellSession monitors a pexpect connection.
        Optionally, a prompt can be forced after
        a percentage of the timeout.
        """

        self.raw_connection = shell_command
        self.check_char = "#"
        self.connected = True
        self.tags: list[str] = ["shell"]

        # FIXME: rename __prompt_str__ to indicate it can be a list or str
        self.__prompt_str__: str | None = None
        self.timeout = shell_command.lava_timeout
        self.logger = logging.getLogger("dispatcher")

    def send(self, character: str, disconnecting: bool = False) -> None:
        if self.connected:
            self.raw_connection.send(character)
        elif not disconnecting:
            raise LAVABug("send")

    def sendline(
        self,
        line: str,
        delay: float = 0.0,
        disconnecting: bool = False,
        check: bool = False,
        timeout: int | float = 15,
    ) -> None:
        if self.connected:
            if not check:
                self.raw_connection.sendline(line, delay=delay)
            else:
                signal = "LAVA_SIGNAL_RETRUNCODE"
                self.raw_connection.sendline(
                    f'{line} ; printf "<{signal} $?>\\n"', delay=delay
                )
                self.logger.debug(
                    f"Checking {line!r} return code... "
                    f"(timeout {seconds_to_str(timeout)})"
                )
                self.raw_connection.expect(
                    [
                        rf"<{signal} (\d+)>",
                        pexpect.TIMEOUT,
                    ],
                    timeout=timeout,
                )
                expect_match = self.raw_connection.match
                if isinstance(expect_match, Match):
                    rc = expect_match.group(1)
                    with contextlib.suppress(TypeError, ValueError):
                        if rc := int(rc):
                            raise JobError(f"{line!r} failed with return code {rc}!")
                else:
                    # Instead of the default TestError, raise JobError with a
                    # specific error message.
                    raise JobError(f"Failed to check {line!r} return code!")

        elif not disconnecting:
            raise LAVABug("sendline called on disconnected connection")

    def sendcontrol(self, char: str) -> None:
        if self.connected:
            self.raw_connection.sendcontrol(char)
        else:
            raise LAVABug("sendcontrol called on disconnected connection")

    def disconnect(self, reason: str) -> None:
        logger = self.logger

        if self.connected:
            try:
                if "telnet" in self.tags:
                    logger.info("Disconnecting from telnet: %s", reason)
                    self.sendcontrol("]")
                    self.sendline("quit", disconnecting=True)
                elif "ssh" in self.tags:
                    logger.info("Disconnecting from ssh: %s", reason)
                    self.sendline("", disconnecting=True)
                    self.sendline("~.", disconnecting=True)
                elif self.name == "LxcSession":
                    logger.info("Disconnecting from lxc: %s", reason)
                    self.sendline("", disconnecting=True)
                    self.sendline("exit", disconnecting=True)
                elif self.name == "QemuSession":
                    logger.info("Disconnecting from qemu: %s", reason)
                elif self.name == "ShellSession":
                    logger.info("Disconnecting from shell: %s", reason)
                else:
                    raise LAVABug("'disconnect' not supported for %s" % self.tags)
            except ValueError:  # protection against file descriptor == -1
                logger.debug("Already disconnected")
        else:
            logger.debug("Already disconnected")

        self.connected = False
        if self.raw_connection:
            with contextlib.suppress(pexpect.ExceptionPexpect):
                self.raw_connection.close(force=True)

    def finalise(self) -> None:
        if self.raw_connection:
            try:
                pid = self.raw_connection.pid
                if pid is not None:  # If shell never started the pid will be None.
                    os_killpg(pid, SIGKILL)
            except OSError:
                self.raw_connection.kill(SIGKILL)
            else:
                self.connected = False
                self.raw_connection.close(force=True)

    # FIXME: rename prompt_str to indicate it can be a list or str
    @property
    def prompt_str(self) -> str | None:
        return self.__prompt_str__

    @prompt_str.setter
    def prompt_str(self, string: str) -> None:
        """
        pexpect allows the prompt to be a single string or a list of strings
        this property simply replaces the previous value with the new one
        whether that is a string or a list of strings.
        To use + the instance of the existing prompt_str must be checked.
        """
        self.logger.debug("Setting prompt string to %r" % string)
        self.__prompt_str__ = string

    @contextlib.contextmanager
    def test_connection(self) -> Iterator[ShellCommand]:
        """
        Yields the actual connection which can be used to interact inside this shell.
        """
        yield self.raw_connection

    def force_prompt_wait(self, remaining: float | None = None) -> int:
        """
        One of the challenges we face is that kernel log messages can appear
        half way through a shell prompt.  So, if things are taking a while,
        we send a newline along to maybe provoke a new prompt.  We wait for
        half the timeout period and then wait for one tenth of the timeout
        6 times (so we wait for 1.1 times the timeout period overall).
        :return: the index into the connection.prompt_str list
        """
        prompt_wait_count = 0
        if not remaining:
            return self.wait()
        # connection_prompt_limit
        partial_timeout = remaining / 2.0
        self.logger.debug(
            "Waiting using forced prompt support (timeout %s)"
            % seconds_to_str(partial_timeout)
        )
        prompt_str = self.prompt_str
        if prompt_str is None:
            raise LAVABug("prompt_str is None")

        while True:
            try:
                return self.raw_connection.expect(prompt_str, timeout=partial_timeout)
            except (pexpect.TIMEOUT, TestError) as exc:
                if prompt_wait_count < 6:
                    self.logger.warning(
                        "%s: Sending %s in case of corruption. Connection timeout %s, retry in %s",
                        exc,
                        self.check_char,
                        seconds_to_str(remaining),
                        seconds_to_str(partial_timeout),
                    )
                    self.logger.debug("pattern: %s", prompt_str)
                    prompt_wait_count += 1
                    partial_timeout = remaining / 10
                    self.sendline(self.check_char)
                    continue
                else:
                    # TODO: is someone expecting pexpect.TIMEOUT?
                    raise
            except ConnectionClosedError as exc:
                self.connected = False
                raise InfrastructureError(str(exc))

    def wait(
        self,
        max_end_time: float | None = None,
        max_searchwindowsize: bool = False,
        job_error_message: str | None = None,
    ) -> int:
        """
        Simple wait without sending blank lines as that causes the menu
        to advance without data which can cause blank entries and can cause
        the menu to exit to an unrecognised prompt.
        """
        if not max_end_time:
            timeout: float = self.timeout.duration
        else:
            timeout = max_end_time - time.monotonic()
        if timeout < 0.0:
            raise LAVABug("Invalid max_end_time value passed to wait()")

        prompt_str = self.prompt_str
        if prompt_str is None:
            raise LAVABug("prompt_str is None")

        try:
            if max_searchwindowsize:
                return self.raw_connection.expect(
                    prompt_str,
                    timeout=timeout,
                    searchwindowsize=None,
                    async_=False,
                )
            else:
                return self.raw_connection.expect(
                    prompt_str, timeout=timeout, async_=False
                )
        except (TestError, pexpect.TIMEOUT):
            raise JobError(job_error_message or "wait for prompt timed out")
        except ConnectionClosedError as exc:
            self.connected = False
            raise InfrastructureError(str(exc))

    def listen_feedback(self, timeout: float, namespace: str | None = None) -> int:
        """
        Listen to output and log as feedback
        Returns the number of characters read.
        """
        index = 0
        if not self.raw_connection:
            # connection has already been closed.
            return index
        if timeout < 0.0:
            raise LAVABug("Invalid timeout value passed to listen_feedback()")
        try:
            self.raw_connection.output_logger.is_feedback = True
            self.raw_connection.output_logger.namespace = namespace
            index = self.raw_connection.expect(
                [".+", pexpect.EOF, pexpect.TIMEOUT], timeout=timeout
            )
        finally:
            self.raw_connection.output_logger.is_feedback = False
            self.raw_connection.output_logger.namespace = None

        if index == 0:
            connection_after = self.raw_connection.after
            # connection_after can be EOF or TIMEOUT
            if isinstance(connection_after, str):
                return len(connection_after)
        return 0


class ExpectShellSession(Action):
    """
    Waits for a shell connection to the device for the current job.
    The shell connection can be over any particular connection,
    all that is needed is a prompt.
    """

    name = "expect-shell-connection"
    description = "Wait for a shell"
    summary = "Expect a shell prompt"

    def __init__(self, job: Job):
        super().__init__(job)
        self.force_prompt = True

    def validate(self) -> None:
        super().validate()
        if "prompts" not in self.parameters:
            self.errors = "Unable to identify test image prompts from parameters."

    def run(self, connection: ShellSession, max_end_time: float | None) -> ShellSession:
        connection = super().run(connection, max_end_time)
        if not connection:
            raise JobError("No connection available.")
        connection.prompt_str = self.parameters["prompts"]
        connection.timeout = self.connection_timeout
        self.logger.debug(
            "Forcing a shell prompt, looking for %s", connection.prompt_str
        )
        connection.sendline("")
        self.wait(connection)
        return connection
