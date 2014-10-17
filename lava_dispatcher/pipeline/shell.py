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

import os
import sys
import time
import logging
import pexpect
import contextlib
from lava_dispatcher.pipeline.action import (
    Action,
    JobError,
    RetryAction,
    Timeout,
)
from lava_dispatcher.pipeline.connection import Connection, CommandRunner


class ShellCommand(pexpect.spawn):  # pylint: disable=too-many-public-methods
    """
    Run a command over a connection using pexpect instead of
    subprocess, i.e. not on the dispatcher itself.
    Takes a Timeout object (to support overrides and logging)

    A ShellCommand is a raw_connection for a ShellConnection instance.
    """

    def __init__(self, command, lava_timeout, cwd=None):
        if not lava_timeout:
            lava_timeout = Timeout('default')
        pexpect.spawn.__init__(
            self, command, timeout=lava_timeout.duration, cwd=cwd, logfile=sys.stdout)
        self.name = "ShellCommand"
        # serial can be slow, races do funny things, so increase delay
        # FIXME: this as to be a constant, written somewhere with all constants
        self.delaybeforesend = 0.05
        self.lava_timeout = lava_timeout
        yaml_log = logging.getLogger("YAML")
        yaml_log.debug({'spawn': {
            lava_timeout.name: lava_timeout.duration,
            'command': self.command
        }})
        # FIXME: consider a logginghandler as with standard actions or use the handler of the calling Action?

    def sendline(self, s='', delay=0, send_char=True):  # pylint: disable=arguments-differ
        """
        Extends pexpect.sendline so that it can support the delay argument which allows a delay
        between sending each character to get around slow serial problems (iPXE).
        pexpect sendline does exactly the same thing: calls send for the string then os.linesep.

        :param s: string to send
        :param delay: delay in milliseconds between sending each character
        :param send_char: send one character or entire string
        """
        self.send(s, delay, send_char)
        self.send(os.linesep, delay)

    def sendcontrol(self, char):
        # FIXME: the getLogger should be done only once
        yaml_log = logging.getLogger("YAML")
        yaml_log.debug("sending control character: %s", char)
        return super(ShellCommand, self).sendcontrol(char)

    def send(self, string, delay=0, send_char=True):  # pylint: disable=arguments-differ
        """
        Extends pexpect.send to support extra arguments, delay and send by character flags.
        """
        # FIXME: the getLogger should be done only once
        yaml_log = logging.getLogger("YAML")
        yaml_log.debug("send (delay_ms=%s): %s ", delay, string)
        sent = 0
        delay = float(delay) / 1000
        if send_char:
            for char in string:
                sent += super(ShellCommand, self).send(char)
                time.sleep(delay)
        else:
            sent = super(ShellCommand, self).send(string)
        return sent

    def expect(self, *args, **kw):
        # FIXME: the getLogger should be done only once
        yaml_log = logging.getLogger("YAML")
        std_log = logging.getLogger("ASCII")

        # FIXME: this produces the most ugly log output of any part of the dispatcher.
        if len(args) == 1:
            yaml_log.debug("expect (%d): '%s'", self.lava_timeout.duration, args[0])
        else:
            yaml_log.debug("expect (%d): '%s'", self.lava_timeout.duration, str(args))

        try:
            proc = super(ShellCommand, self).expect(*args, **kw)
#        except pexpect.TIMEOUT:
#            raise JobError("command timed out.")
        except pexpect.EOF:
            raise RuntimeError(" ".join(self.before.split('\r\n')))
        yaml_log.debug("Prompt matched.")
        return proc

    def empty_buffer(self):
        """Make sure there is nothing in the pexpect buffer."""
        index = 0
        while index == 0:
            index = self.expect(['.+', pexpect.EOF, pexpect.TIMEOUT], timeout=1)


class ShellSession(Connection):

    def __init__(self, job, shell_command):
        """
        The connection takes over result handling for the TestAction, adding individual results to the
        logs every time a test_case is matched, so that if a test definition falls over or times out,
        the results so-far will be retained.
        Each result generates an item in the data context with an ID. This ID can be used later to
        look up each individial testcase result.
        TODO: ensure the stdout for each testcase result is captured and tagged with this ID.
        """
        super(ShellSession, self).__init__(job, shell_command)
        self.__runner__ = None
        self.name = "ShellSession"
        self.data = job.context.pipeline_data

    @property
    def runner(self):
        if self.__runner__ is None:
            device = self.device
            spawned_shell = self.raw_connection  # ShellCommand(pexpect.spawn)
            prompt_str = device.parameters['test_image_prompts']
            prompt_str_includes_rc = True  # FIXME
#            prompt_str_includes_rc = device.config.tester_ps1_includes_rc
            # FIXME: although CommandRunner has been ported, NetworkRunner and others need to be rewritten for logging & timeout support.
            # The Connection for a CommandRunner in the pipeline needs to be a ShellCommand, not logging_spawn
            self.__runner__ = CommandRunner(spawned_shell, prompt_str, prompt_str_includes_rc)
        return self.__runner__

    def run_command(self, command):
        self.runner.run(command)

    @contextlib.contextmanager
    def test_connection(self):
        """
        Yields the actual connection which can be used to interact inside this shell.
        """
        if self.__runner__ is None:
            device = self.device
            spawned_shell = self.raw_connection  # ShellCommand(pexpect.spawn)
            prompt_str = device.parameters['test_image_prompts']
            prompt_str_includes_rc = True  # FIXME
#            prompt_str_includes_rc = device.config.tester_ps1_includes_rc
            # FIXME: although CommandRunner has been ported, NetworkRunner and others need to be rewritten for logging & timeout support.
            # The Connection for a CommandRunner in the pipeline needs to be a ShellCommand, not logging_spawn
            self.__runner__ = CommandRunner(spawned_shell, prompt_str,
                                            prompt_str_includes_rc)
        yield self.__runner__.get_connection()

    def wait(self):
        yaml_log = logging.getLogger("YAML")
        yaml_log.debug("sending new line. Waiting for prompt")
        self.raw_connection.sendline("")
        try:
            self.runner.wait_for_prompt()
        except pexpect.TIMEOUT:
            raise JobError("wait for prompt timed out")


class ExpectShellSession(Action):
    """
    Waits for a shell connection to the device for the current job.
    """

    def __init__(self):
        super(ExpectShellSession, self).__init__()
        self.name = "expect-shell-connection"
        self.summary = "Expect a shell prompt"
        self.description = "Wait for a shell"

    def run(self, connection, args=None):
        self._log("Waiting for prompt")
        connection.wait()  # FIXME: should be a regular RetryAction operation
        return connection
