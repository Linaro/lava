# Copyright (C) 2014-2019 Linaro Limited
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

import contextlib
import logging
import pexpect
import sre_constants
import time
from lava_dispatcher.action import Action
from lava_common.exceptions import (
    ConnectionClosedError,
    InfrastructureError,
    JobError,
    LAVABug,
    TestError,
)
from lava_common.timeout import Timeout
from lava_dispatcher.connection import Connection
from lava_common.constants import LINE_SEPARATOR
from lava_dispatcher.utils.strings import seconds_to_str


class ShellLogger:
    """
    Builds a YAML log message out of the incremental output of the pexpect.spawn
    using the logfile support built into pexpect.
    """

    def __init__(self, logger):
        self.line = ""
        self.logger = logger
        self.is_feedback = False

    def write(self, new_line):
        replacements = {
            "\n\n": "\n",  # double lines to single
            "\r": "",
            '"': '\\"',  # escape double quotes for YAML syntax
            "\x1b": "",  # remove escape control characters
        }
        for key, value in replacements.items():
            new_line = new_line.replace(key, value)
        lines = self.line + new_line

        # Print one full line at a time. A partial line is kept in memory.
        if "\n" in lines:
            last_ret = lines.rindex("\n")
            self.line = lines[last_ret + 1 :]
            lines = lines[:last_ret]
            for line in lines.split("\n"):
                if self.is_feedback:
                    if self.namespace:
                        self.logger.feedback(line, namespace=self.namespace)
                    else:
                        self.logger.feedback(line)
                else:
                    self.logger.target(line)
        else:
            self.line = lines
        return

    def flush(self, force=False):
        if force and self.line:
            self.write("\n")


class ShellCommand(pexpect.spawn):
    """
    Run a command over a connection using pexpect instead of
    subprocess, i.e. not on the dispatcher itself.
    Takes a Timeout object (to support overrides and logging)

    https://pexpect.readthedocs.io/en/stable/api/pexpect.html#spawn-class

    Window size is managed to limit impact on performance.
    maxread is left at default to ensure the entire log is captured.

    A ShellCommand is a raw_connection for a ShellConnection instance.
    """

    def __init__(self, command, lava_timeout, logger=None, cwd=None, window=2000):
        if isinstance(window, str):
            # constants need to be stored as strings.
            try:
                window = int(window)
            except ValueError:
                raise LAVABug(
                    "ShellCommand was passed an invalid window size of %s bytes."
                    % window
                )
        if not lava_timeout or not isinstance(lava_timeout, Timeout):
            raise LAVABug("ShellCommand needs a timeout set by the calling Action")
        if not logger:
            raise LAVABug("ShellCommand needs a logger")
        pexpect.spawn.__init__(
            self,
            command,
            timeout=lava_timeout.duration,
            cwd=cwd,
            logfile=ShellLogger(logger),
            encoding="utf-8",
            # Data before searchwindowsize point is preserved, but not searched.
            searchwindowsize=None,  # pattern match the entire buffer
            maxread=window,  # limit the size of the buffer. 1 to turn off buffering
            codec_errors="replace",
        )
        self.name = "ShellCommand"
        self.logger = logger
        # set a default newline character, but allow actions to override as necessary
        self.linesep = LINE_SEPARATOR
        self.lava_timeout = lava_timeout

    def sendline(self, s="", delay=0):
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
        self.logger.input(s + self.linesep)
        self.send(s, delay, send_char)
        self.send(self.linesep, delay)

    def sendcontrol(self, char):
        self.logger.input(char)
        return super().sendcontrol(char)

    def send(self, string, delay=0, send_char=True):
        """
        Extends pexpect.send to support extra arguments, delay and send by character flags.
        """
        sent = 0
        if not string:
            return sent
        delay = float(delay) / 1000
        if send_char:
            for char in string:
                sent += super().send(char)
                time.sleep(delay)
        else:
            sent = super().send(string)
        return sent

    def expect(self, *args, **kw):
        """
        No point doing explicit logging here, the SignalDirector can help
        the TestShellAction make much more useful reports of what was matched
        """
        try:
            proc = super().expect(*args, **kw)
        except sre_constants.error as exc:
            msg = "Invalid regular expression '%s': %s" % (exc.pattern, exc.msg)
            raise TestError(msg)
        except pexpect.TIMEOUT:
            raise TestError("ShellCommand command timed out.")
        except ValueError as exc:
            raise TestError(exc)
        except pexpect.EOF:
            # FIXME: deliberately closing the connection (and starting a new one) needs to be supported.
            raise ConnectionClosedError("Connection closed")
        return proc

    def empty_buffer(self):
        """Make sure there is nothing in the pexpect buffer."""
        index = 0
        while index == 0:
            index = self.expect([".+", pexpect.EOF, pexpect.TIMEOUT], timeout=1)

    def flush(self):
        """ Will be called by pexpect itself when closing the connection """
        self.logfile.flush(force=True)


class ShellSession(Connection):

    name = "ShellSession"

    def __init__(self, job, shell_command):
        """
        A ShellSession monitors a pexpect connection.
        Optionally, a prompt can be forced after
        a percentage of the timeout.
        """
        super().__init__(job, shell_command)
        # FIXME: rename __prompt_str__ to indicate it can be a list or str
        self.__prompt_str__ = None
        self.spawn = shell_command
        self.__runner__ = None
        self.timeout = shell_command.lava_timeout
        self.__logger__ = None
        self.tags = ["shell"]

    @property
    def logger(self):
        if not self.__logger__:
            self.__logger__ = logging.getLogger("dispatcher")
        return self.__logger__

    # FIXME: rename prompt_str to indicate it can be a list or str
    @property
    def prompt_str(self):
        return self.__prompt_str__

    @prompt_str.setter
    def prompt_str(self, string):
        """
        pexpect allows the prompt to be a single string or a list of strings
        this property simply replaces the previous value with the new one
        whether that is a string or a list of strings.
        To use + the instance of the existing prompt_str must be checked.
        """
        self.logger.debug("Setting prompt string to %r" % string)
        self.__prompt_str__ = string

    @contextlib.contextmanager
    def test_connection(self):
        """
        Yields the actual connection which can be used to interact inside this shell.
        """
        yield self.raw_connection

    def force_prompt_wait(self, remaining=None):
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
        while True:
            try:
                return self.raw_connection.expect(
                    self.prompt_str, timeout=partial_timeout
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

    def wait(self, max_end_time=None):
        """
        Simple wait without sendling blank lines as that causes the menu
        to advance without data which can cause blank entries and can cause
        the menu to exit to an unrecognised prompt.
        """
        if not max_end_time:
            timeout = self.timeout.duration
        else:
            timeout = max_end_time - time.time()
        if timeout < 0:
            raise LAVABug("Invalid max_end_time value passed to wait()")
        try:
            return self.raw_connection.expect(self.prompt_str, timeout=timeout)
        except (TestError, pexpect.TIMEOUT):
            raise JobError("wait for prompt timed out")
        except ConnectionClosedError as exc:
            self.connected = False
            raise InfrastructureError(str(exc))

    def listen_feedback(self, timeout, namespace=None):
        """
        Listen to output and log as feedback
        Returns the number of characters read.
        """
        index = 0
        if not self.raw_connection:
            # connection has already been closed.
            return index
        if timeout < 0:
            raise LAVABug("Invalid timeout value passed to listen_feedback()")
        try:
            # TODO: is this not matching prompts?
            self.raw_connection.logfile.is_feedback = True
            self.raw_connection.logfile.namespace = namespace
            index = self.raw_connection.expect(
                [".+", pexpect.EOF, pexpect.TIMEOUT], timeout=timeout
            )
        finally:
            self.raw_connection.logfile.is_feedback = False
            self.raw_connection.logfile.namespace = None

        if index == 0:
            return len(self.raw_connection.after)
        return 0


class ExpectShellSession(Action):
    """
    Waits for a shell connection to the device for the current job.
    The shell connection can be over any particular connection,
    all that is needed is a prompt.
    """

    compatibility = 2
    name = "expect-shell-connection"
    description = "Wait for a shell"
    summary = "Expect a shell prompt"

    def __init__(self):
        super().__init__()
        self.force_prompt = True

    def validate(self):
        super().validate()
        if "prompts" not in self.parameters:
            self.errors = "Unable to identify test image prompts from parameters."

    def run(self, connection, max_end_time):
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
