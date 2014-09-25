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
import logging
import decimal
from lava_dispatcher.pipeline.action import JobError


class BaseSignalHandler(object):

    def __init__(self, testdef_obj=None):
        """
        For compatibility, any testdef_obj passed in is accepted, but ignored.
        """
        self.testdef_obj = testdef_obj

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


class SignalMatch(object):

    def __init__(self, logger):
        self.logger = logger

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
                    raise JobError("Invalid measurement %s", ret)

            elif key == 'result':
                if res['result'] in fixupdict:
                    res['result'] = fixupdict[res['result']]
                if res['result'] not in ('pass', 'fail', 'skip', 'unknown'):
                    res['result'] = 'unknown'
                    self.logger.warning('Setting result to "unknown"')
                    raise JobError('Bad test result: %s', res['result'])

        if 'test_case_id' not in res:
            raise JobError(
                """Test case results without test_case_id (probably a sign of an """
                """incorrect parsing pattern being used): %s""", res)

        if 'result' not in res:
            self.logger.warning('Setting result to "unknown"')
            res['result'] = 'unknown'
            raise JobError(
                """Test case results without result (probably a sign of an """
                """incorrect parsing pattern being used): %s""", res)

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
        self.data = self.job.context.pipeline_data
        self.raw_connection = raw_connection
        self.results = {}
        self.match = None

    def sendline(self, line):
        self.raw_connection.sendline(line)

    def finalise(self):
        if self.raw_connection:
            yaml_log = logging.getLogger("YAML")
            try:
                os.killpg(self.raw_connection.pid, signal.SIGKILL)
                yaml_log.debug("Finalizing child process group with PID %d", self.raw_connection.pid)
            except OSError:
                self.raw_connection.kill(9)
                yaml_log.debug("Finalizing child process with PID %d", self.raw_connection.pid)
            self.raw_connection.close()
