# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import contextlib
import time
from contextlib import contextmanager
from os import killpg as os_killpg
from re import Pattern
from re import error as re_error
from re import split as re_split
from signal import SIGKILL
from typing import TYPE_CHECKING

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
    from collections.abc import Iterator

    from lava_common.log import YAMLLogger
    from lava_dispatcher.job import Job


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


class ShellSession:
    name = "ShellSession"

    def __init__(
        self,
        command: str,
        lava_timeout: Timeout,
        logger: YAMLLogger,
        cwd: str | None = None,
        window: int = 2000,
    ):
        """
        A ShellSession monitors a pexpect connection.
        Optionally, a prompt can be forced after
        a percentage of the timeout.
        """
        if isinstance(window, str):
            # constants need to be stored as strings.
            try:
                window = int(window)
            except ValueError:
                raise LAVABug(
                    "ShellSession was passed an invalid window size of %s bytes."
                    % window
                )
        searchwindowsize = 2 * window
        if not lava_timeout or not isinstance(lava_timeout, Timeout):
            raise LAVABug("ShellSession needs a timeout set by the calling Action")
        if not logger:
            raise LAVABug("ShellSession needs a logger")

        shell_command = pexpect.spawn(
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
        self.shell_output_logger = ShellLogger(logger)
        shell_command.logfile_read = self.shell_output_logger
        self.shell_input_logger = ShellLogger(logger, is_input=True)
        shell_command.logfile_send = self.shell_input_logger
        # delayafterterminate allow for some spare time for a process to terminate
        # If the system is loaded
        # See https://github.com/pexpect/pexpect/issues/462
        shell_command.delayafterterminate = 1.0
        shell_command.delaybeforesend = (
            None  # LAVA implements its own delay between characters.
        )
        # lava-run is single threaded, there is no concern about GIL not being released
        # between read calls. Remove delay after read.
        # Typeshed type hints has incorrectly marked `delayafterread` as float only.
        shell_command.delayafterread = None  # type: ignore[assignment, unused-ignore]
        # set a default newline character, but allow actions to override as necessary
        self.linesep = LINE_SEPARATOR

        self.raw_connection: pexpect.spawn[str] = shell_command
        self.check_char = "#"
        self.connected = True
        self.tags: list[str] = ["shell"]

        # FIXME: rename __prompt_str__ to indicate it can be a list or str
        self.__prompt_str__: str | None = None
        self.timeout = lava_timeout
        self.logger = logger

    def _sendline_wrapper(self, s: str = "", delay: float = 0.0) -> None:
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
        self._send_wrapper(s, delay, send_char)
        self._send_wrapper(self.linesep, delay)

    def _send_wrapper(
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
            for char in string:
                sent += self.raw_connection.send(char)
                time.sleep(delay)
        else:
            sent = self.raw_connection.send(string)
        return sent

    @contextmanager
    def _expect_exc_wrapper(self) -> Iterator[None]:
        """
        No point doing explicit logging here, the SignalDirector can help
        the TestShellAction make much more useful reports of what was matched
        """
        try:
            yield None
        except re_error as exc:
            msg = f"Invalid regular expression {exc.pattern!r}: {exc.msg}"
            raise TestError(msg)
        except pexpect.TIMEOUT:
            raise TestError("ShellSession command timed out.")
        except ValueError as exc:
            raise TestError(exc)
        except pexpect.EOF:
            # FIXME: deliberately closing the connection (and starting a new one) needs to be supported.
            raise ConnectionClosedError("Connection closed")

    def send(self, character: str, disconnecting: bool = False) -> None:
        if self.connected:
            self._send_wrapper(character)
        elif not disconnecting:
            raise LAVABug("send")

    def sendline(
        self,
        line: str,
        delay: int = 0,
        disconnecting: bool = False,
        check: bool = False,
        timeout: int | float = 15,
    ) -> None:
        if self.connected:
            if not check:
                self._sendline_wrapper(line, delay=delay)
            else:
                signal: str = "LAVA_SIGNAL_RETRUNCODE"
                self._send_wrapper(f'{line} ; printf "<{signal} $?>\\n"', delay=delay)
                self.logger.debug(
                    f"Checking {line!r} return code... "
                    f"(timeout {seconds_to_str(timeout)})"
                )
                try:
                    self.raw_connection.expect(
                        [
                            rf"<{signal} (\d+)>",
                            pexpect.TIMEOUT,
                        ],
                        timeout=timeout,
                    )
                    match = self.raw_connection.match
                except pexpect.TIMEOUT:
                    raise JobError(f"Failed to check {line!r} return code!")
                except pexpect.EOF:
                    raise ConnectionClosedError("Connection closed")
                except re_error as exc:
                    raise TestError(
                        f"Invalid regular expression {exc.pattern!r}: {exc.msg}"
                    )
                except ValueError as exc:
                    raise TestError(exc)

                if isinstance(match, Pattern):
                    rc = match.group(1)
                    with contextlib.suppress(TypeError, ValueError):
                        if rc := int(rc):
                            raise JobError(f"{line!r} failed with return code {rc}!")

        elif not disconnecting:
            raise LAVABug("sendline called on disconnected connection")

    def sendcontrol(self, char: str) -> int:
        if self.connected:
            self.logger.debug("Sending character: %r", char)
            return self.raw_connection.sendcontrol(char)
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

        if self.connected:
            self.connected = False
            with contextlib.suppress(pexpect.ExceptionPexpect):
                self.shell_input_logger.flush(True)
                self.shell_output_logger.flush(True)
                self.raw_connection.close(force=True)

    def finalise(self) -> None:
        if self.connected:
            try:
                pid = self.raw_connection.pid
                if pid is not None:  # If shell never started the pid will be None.
                    os_killpg(pid, SIGKILL)
            except OSError:
                self.raw_connection.kill(SIGKILL)
            else:
                self.connected = False
                self.raw_connection.close(force=True)

        self.shell_input_logger.flush(True)
        self.shell_output_logger.flush(True)

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
    def test_connection(self) -> Iterator["TestConnection"]:
        """
        Yields a TestConnection wrapper that provides expect() with proper
        exception handling while delegating other attributes to the raw connection.
        """
        yield TestConnection(self.raw_connection, self)


class TestConnection:
    """
    Wrapper around pexpect.spawn used by test actions.
    Provides expect() with proper exception handling while delegating
    other attributes (match, after, timeout, sendline, etc.) to the raw connection.
    """

    def __init__(self, raw_connection: pexpect.spawn[str], shell_session: "ShellSession"):
        self._raw = raw_connection
        self._session = shell_session

    def expect(self, *args, **kwargs) -> int:
        """Wrapper around raw_connection.expect() with proper exception handling."""
        with self._session._expect_exc_wrapper():
            return self._raw.expect(*args, **kwargs)

    def __getattr__(self, name: str):
        """Delegate all other attributes to the raw connection."""
        return getattr(self._raw, name)

    def __setattr__(self, name: str, value) -> None:
        """Delegate attribute setting to raw connection (except internal attrs)."""
        if name in ("_raw", "_session"):
            super().__setattr__(name, value)
        else:
            setattr(self._raw, name, value)

    def sendline(self, *args, **kwargs):
        """Delegate sendline to the shell session for proper logging."""
        return self._session.sendline(*args, **kwargs)

    def send(self, *args, **kwargs):
        """Delegate send to the shell session."""
        return self._session.send(*args, **kwargs)

    def sendcontrol(self, *args, **kwargs):
        """Delegate sendcontrol to the shell session."""
        return self._session.sendcontrol(*args, **kwargs)

    def readline(self, *args, **kwargs):
        """Delegate readline to the raw connection."""
        return self._raw.readline(*args, **kwargs)

    def readline_noncanonical(self, *args, **kwargs):
        """Delegate readline_noncanonical to the raw connection."""
        return self._raw.readline_noncanonical(*args, **kwargs)

    def write(self, *args, **kwargs):
        """Delegate write to the raw connection."""
        return self._raw.write(*args, **kwargs)

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
                with self._expect_exc_wrapper():
                    return self.raw_connection.expect(
                        prompt_str, timeout=partial_timeout
                    )
            except (pexpect.TIMEOUT, TestError) as exc:
                if prompt_wait_count < 6:
                    self.logger.warning(
                        "%s: Sending %s in case of corruption. Connection timeout %s, retry in %s",
                        exc,
                        self.check_char,
                        seconds_to_str(remaining),
                        seconds_to_str(partial_timeout),
                    )
                    self.logger.debug("pattern: %s", self.prompt_str)
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
                with self._expect_exc_wrapper():
                    return self.raw_connection.expect(
                        prompt_str, timeout=timeout, searchwindowsize=None
                    )
            else:
                with self._expect_exc_wrapper():
                    return self.raw_connection.expect(prompt_str, timeout=timeout)
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
            self.shell_output_logger.is_feedback = True
            self.shell_output_logger.namespace = namespace
            index = self.raw_connection.expect(
                [".+", pexpect.EOF, pexpect.TIMEOUT], timeout=timeout
            )
        finally:
            self.shell_output_logger.is_feedback = False
            self.shell_output_logger.namespace = None

        if index == 0:
            return len(self.raw_connection.after)  # type: ignore[arg-type]

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
            self.errors_add("Unable to identify test image prompts from parameters.")

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
