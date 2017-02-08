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
import signal
import decimal
import logging
from lava_dispatcher.pipeline.action import TestError, Timeout, InternalObject

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

    def match(self, data, fixupdict=None):  # pylint: disable=no-self-use
        if not fixupdict:
            fixupdict = {}

        res = {}
        for key in data:
            # Special cases for 'measurement'
            if key == 'measurement':
                try:
                    res['measurement'] = decimal.Decimal(data['measurement'])
                except decimal.InvalidOperation:
                    raise TestError("Invalid measurement %s", data['measurement'])

            # and 'result'
            elif key == 'result':
                res['result'] = data['result']
                if data['result'] in fixupdict:
                    res['result'] = fixupdict[data['result']]
                if res['result'] not in ('pass', 'fail', 'skip', 'unknown'):
                    res['result'] = 'unknown'
                    raise TestError('Bad test result: %s' % data['result'])

            # or just copy the data
            else:
                res[key] = data[key]

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
        self.check_char = '#'

    def corruption_check(self):
        self.sendline(self.check_char)

    def sendline(self, line, delay=0, disconnecting=False):
        if self.connected:
            self.raw_connection.sendline(line, delay=delay)
        elif not disconnecting:
            raise RuntimeError()

    def sendcontrol(self, char):
        if self.connected:
            self.raw_connection.sendcontrol(char)
        else:
            raise RuntimeError()

    def force_prompt_wait(self, remaining):
        raise NotImplementedError()

    def wait(self, max_end_time=None):
        raise NotImplementedError()

    def disconnect(self, reason):
        raise NotImplementedError()

    def finalise(self):
        if self.raw_connection:
            try:
                os.killpg(self.raw_connection.pid, signal.SIGKILL)
                # self.logger.debug("Finalizing child process group with PID %d" % self.raw_connection.pid)
            except OSError:
                self.raw_connection.kill(9)
                # self.logger.debug("Finalizing child process with PID %d" % self.raw_connection.pid)
            self.raw_connection.close()


class Protocol(object):
    """
    Similar to a Connection object, provides a transport layer for the dispatcher.
    Uses a pre-defined API instead of pexpect using Shell.

    Testing a protocol involves either basing the protocol on SocketServer and using threading
    or adding a main function in the protocol python file and including a demo server script which
    can be run on the command line - using a different port to the default. However, this is likely
    to be of limited use because testing the actual API calls will need a functional test.

    If a Protocol requires another Protocol to be available in order to run, the depending
    Protocol *must* specify a higher level. All Protocol objects of a lower level are setup and
    run before Protocol objects of a higher level. Protocols with the same level can be setup or run
    in an arbitrary order (as the original source data is a dictionary).
    """
    name = 'protocol'
    level = 0

    def __init__(self, parameters, job_id):
        self.logger = logging.getLogger("dispatcher")
        self.poll_timeout = Timeout(self.name)
        self.parameters = None
        self.__errors__ = []
        self.parameters = parameters
        self.configured = False
        self.job_id = job_id

    @classmethod
    def select_all(cls, parameters):
        """
        Multiple protocols can apply to the same job, each with their own parameters.
        Jobs may have zero or more protocols selected.
        """
        candidates = cls.__subclasses__()  # pylint: disable=no-member
        return [(c, c.level) for c in candidates if c.accepts(parameters)]

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

    def configure(self, device, job):  # pylint: disable=unused-argument
        self.configured = True

    def finalise_protocol(self, device=None):
        raise NotImplementedError()

    def check_timeout(self, duration, data):  # pylint: disable=unused-argument,no-self-use
        """
        Use if particular protocol calls can require a connection timeout
        larger than the default_connection_duration.
        :param duration: A minimum number of seconds
        :param data: the API call
        :return: True if checked, False if no limit is specified by the protocol.
        raises JobError if the API call is invalid.
        """
        return False

    def _api_select(self, data):  # pylint: disable=no-self-use
        if not data:
            return None
        raise NotImplementedError()

    def __call__(self, args):  # pylint: disable=no-self-use
        """ Makes the Protocol callable so that actions can send messages just using the protocol.
        This function may block until the specified API call returns. Some API calls may involve a
        substantial period of polling.
        :param args: arguments of the API call to make
        :return: A Python object containing the reply dict from the API call
        """
        return self._api_select(args)

    def collate(self, reply_dict, params_dict):  # pylint: disable=unused-argument,no-self-use
        return None
