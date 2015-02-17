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
import time
import pexpect
import signal
import decimal
import logging
from lava_dispatcher.pipeline.action import TestError, Timeout, InternalObject
from lava_dispatcher.pipeline.utils.shell import wait_for_prompt

# pylint: disable=too-many-public-methods,too-many-instance-attributes


class BaseSignalHandler(object):
    """
    Used to extend the SignalDirector to allow protocols to respond to signals.
    """

    def __init__(self, protocol=None):
        self.protocol = protocol

    def __call__(self, *args, **kwargs):
        pass

    def start(self):
        pass

    def end(self):
        pass

    def starttc(self, test_case_id):
        pass

    def endtc(self, test_case_id):
        pass

    @callable
    def custom_signal(self, signame, params):
        pass

    def postprocess_test_run(self, test_run):
        pass


class SignalMatch(InternalObject):  # pylint: disable=too-few-public-methods

    def match(self, data, fixupdict=None):
        if not fixupdict:
            fixupdict = {}

        res = {}
        for key in data:
            res[key] = data[key]

            if key == 'measurement':
                try:
                    res[key] = decimal.Decimal(res[key])
                except decimal.InvalidOperation:
                    ret = res['measurement']
                    del res['measurement']
                    raise TestError("Invalid measurement %s", ret)

            elif key == 'result':
                if res['result'] in fixupdict:
                    res['result'] = fixupdict[res['result']]
                if res['result'] not in ('pass', 'fail', 'skip', 'unknown'):
                    res['result'] = 'unknown'
                    raise TestError('Bad test result: %s', res['result'])

        if 'test_case_id' not in res:
            raise TestError("Test case results without test_case_id (probably a sign of an "
                            "incorrect parsing pattern being used): %s", res)

        if 'result' not in res:
            res['result'] = 'unknown'
            raise TestError("Test case results without result (probably a sign of an "
                            "incorrect parsing pattern being used): %s", res)

        return res


class Connection(object):
    """
    A raw_connection is an arbitrary instance of a standard Python (or added LAVA) class
    designed to implement an interactive connection onto the device. The raw_connection
    needs to be able to send commands, use a timeout, handle errors, log the output,
    match on regular expressions for the output, report the pid of the spawned process
    and cause the spawned process to close/terminate.
    The current implementation uses a pexpect.spawn wrapper. For a standard Shell
    connection, that is the ShellCommand class.
    Each different wrapper of pexpect.spawn (and any other wrappers later designed)
    needs to be a separate class supported by another class inheriting from Connection.

    A TestJob can have multiple connections but only one device and all Connection objects
    must reference that one device.

    Connecting between devices is handled inside the YAML test definition, whether by
    multinode or by configured services inside the test image.
    """
    def __init__(self, job, raw_connection):
        self.device = job.device
        self.job = job
        # provide access to the context data of the running job
        self.data = self.job.context
        self.raw_connection = raw_connection
        self.results = {}
        self.match = None
        self.connected = True

    def sendline(self, line):
        if self.connected:
            self.raw_connection.sendline(line)
        else:
            raise RuntimeError()  # FIXME:

    def disconnect(self, reason):
        raise NotImplementedError()

    def finalise(self):
        if self.raw_connection:
            try:
                os.killpg(self.raw_connection.pid, signal.SIGKILL)
                # FIXME: determine how to access the zmq logger
                # self.logger.debug("Finalizing child process group with PID %d" % self.raw_connection.pid)
            except OSError:
                self.raw_connection.kill(9)
                # self.logger.debug("Finalizing child process with PID %d" % self.raw_connection.pid)
            self.raw_connection.close()


class CommandRunner(object):
    """
    A convenient way to run a shell command and wait for a shell prompt.

    Higher level functions must be done elsewhere, e.g. using Diagnostics
    """

    def __init__(self, connection, prompt_str, prompt_str_includes_rc):
        """

        :param connection: A pexpect.spawn-like object.
        :param prompt_str: The shell prompt to wait for.
        :param prompt_str_includes_rc: Whether prompt_str includes a pattern
            matching the return code of the command.
        """
        self._connection = connection
        self._prompt_str = prompt_str
        self._prompt_str_includes_rc = prompt_str_includes_rc
        self.match_id = None
        self.match = None

    def change_prompt(self, string):
        # self.logger.debug("Changing prompt to %s" % string)
        self._prompt_str = string

    def wait_for_prompt(self, timeout=-1):
        wait_for_prompt(self._connection, self._prompt_str, timeout)

    def get_connection(self):
        return self._connection

    def run(self, cmd, response=None, timeout=-1, wait_prompt=True):
        """Run `cmd` and wait for a shell response.

        :param cmd: The command to execute.
        :param response: A pattern or sequences of patterns to pass to
            .expect().
        :param timeout: How long to wait for 'response' (if specified) and the
            shell prompt, defaulting to forever.
        :return: The exit value of the command, if wait_for_rc not explicitly
            set to False during construction.
        """
        self._connection.empty_buffer()
        self._connection.sendline(cmd)
        start = time.time()
        if response is not None:
            self.match_id = self._connection.expect(response, timeout=timeout)
            self.match = self._connection.match
            if self.match == pexpect.TIMEOUT:
                return None
            # If a non-trivial timeout was specified, it is held to apply to
            # the whole invocation, so now reduce the time we'll wait for the
            # shell prompt.
            if timeout > 0:
                timeout -= time.time() - start
                # But not too much; give at least a little time for the shell
                # prompt to appear.
                if timeout < 1:
                    timeout = 1
        else:
            self.match_id = None
            self.match = None

        if wait_prompt:
            self.wait_for_prompt(timeout)

            if self._prompt_str_includes_rc:
                return_code = int(self._connection.match.group(1))
                if return_code != 0:
                    raise TestError("executing %r failed with code %s" % (cmd, return_code))
            else:
                return_code = None
        else:
            return_code = None

        return return_code


class Protocol(object):  # pylint: disable=abstract-class-not-used
    """
    Similar to a Connection object, provides a transport layer for the dispatcher.
    Uses a pre-defined API instead of pexpect using Shell.

    Testing a protocol involves either basing the protocol on SocketServer and using threading
    or adding a main function in the protocol python file and including a demo server script which
    can be run on the command line - using a different port to the default. However, this is likely
    to be of limited use because testing the actual API calls will need a functional test.
    """
    name = 'protocol'

    def __init__(self, parameters):
        # FIXME: allow the bare logger to use the zmq socket
        self.logger = logging.getLogger("root")
        self.poll_timeout = Timeout(self.name)
        self.parameters = None
        self.__errors__ = []
        self.parameters = parameters

    @classmethod
    def select_all(cls, parameters):
        """
        Multiple protocols can apply to the same job, each with their own parameters.
        Jobs may have zero or more protocols selected.
        """
        candidates = cls.__subclasses__()  # pylint: disable=no-member
        return [c for c in candidates if c.accepts(parameters)]

    @property
    def errors(self):
        return self.__errors__

    @errors.setter
    def errors(self, error):
        self.__errors__.append(error)

    @property
    def valid(self):
        return len([x for x in self.errors if x]) == 0

    def set_up(self):
        raise NotImplementedError()

    def finalise_protocol(self):
        raise NotImplementedError()

    def _api_select(self, data):
        if not data:
            return None
        raise NotImplementedError()

    def __call__(self, args):
        """ Makes the Protocol callable so that actions can send messages just using the protocol.
        This function may block until the specified API call returns. Some API calls may involve a
        substantial period of polling.
        :param args: arguments of the API call to make
        :return: A Python object containing the reply dict from the API call
        """
        return self._api_select(args)

    def collate(self, reply_dict, params_dict):
        return None
