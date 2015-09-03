# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
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

import atexit
import logging
import os
import subprocess
import sys
import tempfile

from time import sleep
from subprocess import CalledProcessError

from lava_dispatcher.config import get_device_config
from lava_dispatcher.client.base import LavaClient
from lava_dispatcher.test_data import LavaTestData
from lava_dispatcher.utils import (
    logging_spawn,
    rmtree,
)
from lava_dispatcher.errors import (
    OperationFailed,
)


class Flusher(object):
    """
    A Decorator for stream objects that makes all writes flush immediately
    """
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


class Outputter(object):
    """
    Handles the problem of where to send the output. Always sends to stdout,
    and if you pass an output directory it will also store the log in a file
    called output.txt inside that directory.

    During initialization, also sets up the logging subsystem to use the same
    output.
    """

    def __init__(self, output_dir):

        self._output_dir = output_dir
        if output_dir:
            output_txt = os.path.join(output_dir, 'output.txt')
            output_pipe = subprocess.Popen(['tee', output_txt], stdin=subprocess.PIPE)
            self.logfile_read = Flusher(output_pipe.stdin)
        else:
            self.logfile_read = Flusher(sys.stdout)

        log_handler = logging.StreamHandler(self.logfile_read)
        FORMAT = '<LAVA_DISPATCHER>%(asctime)s %(levelname)s: %(message)s'
        DATEFMT = '%Y-%m-%d %I:%M:%S %p'
        log_handler.setFormatter(
            logging.Formatter(fmt=FORMAT, datefmt=DATEFMT))
        del logging.root.handlers[:]
        del logging.root.filters[:]
        logging.root.addHandler(log_handler)

    @property
    def output_dir(self):
        return self._output_dir

    def write_named_data(self, name, data):
        if self.output_dir is None:
            return
        with open(os.path.join(self.output_dir, name), 'w') as outf:
            outf.write(data)


class LavaContext(object):
    def __init__(self, target, dispatcher_config, oob_file, job_data, output_dir):
        self.config = dispatcher_config
        self.job_data = job_data
        self.output = Outputter(output_dir)
        self.logfile_read = self.output.logfile_read
        self.device_config = get_device_config(target)
        self._client = LavaClient(self, self.device_config)
        self.test_data = LavaTestData()
        self.oob_file = oob_file
        self.selinux = None
        self._host_result_dir = None
        self.any_device_bundles = False
        self.repo_keys = ['git-repo', 'bzr-repo', 'tar-repo']

    @property
    def client(self):
        return self._client

    @property
    def any_host_bundles(self):
        return (self._host_result_dir is not None and
                len(os.listdir(self._host_result_dir)) > 0)

    @property
    def host_result_dir(self):
        if self._host_result_dir is None:
            self._host_result_dir = tempfile.mkdtemp()
            atexit.register(rmtree, self._host_result_dir)
        return self._host_result_dir

    def get_device_version(self):
        return self.client.target_device.get_device_version()

    def spawn(self, command, cwd=None, timeout=30):
        proc = logging_spawn(command, cwd, timeout)
        proc.logfile_read = self.logfile_read
        return proc

    def log(self, msg):
        self.logfile_read.write(msg)
        if not msg.endswith('\n'):
            self.logfile_read.write('\n')

    def run_command(self, command, failok=True):
        """run command 'command' with output going to output-dir if specified"""
        if isinstance(command, (str, unicode)):
            command = ['nice', 'sh', '-c', command]
        logging.debug("Executing on host : '%r'" % command)
        output_args = {
            'stdout': self.logfile_read,
            'stderr': subprocess.STDOUT,
        }
        if failok:
            rc = subprocess.call(command, **output_args)
        else:
            rc = subprocess.check_call(command, **output_args)
        return rc

    def run_command_with_retries(self, command):
        retries = 0
        successful = False
        error = None
        num_retries = self.config.host_command_retries

        while (retries < num_retries) and (not successful):
            try:
                self.run_command(command, failok=False)
            except CalledProcessError as e:
                error = e
                retries += 1
                sleep(1)
                continue
            successful = True

        if not successful:
            msg = "Failed to execute command '%s' on host (%s)" % (command, error)
            logging.exception(msg)
            raise OperationFailed(msg)

    def run_command_get_output(self, command):
        """run command 'command' then return the command output"""
        if isinstance(command, (str, unicode)):
            command = ['sh', '-c', command]
        logging.debug("Executing on host : '%r'" % command)
        return subprocess.check_output(command)

    def finish(self):
        self.client.finish()

    def assign_transport(self, transport):
        self.transport = transport

    def assign_group_data(self, group_data):
        """
        :param group_data: Arbitrary data related to the
        group configuration, passed in via the GroupDispatcher
        Used by lava-group
        """
        self.group_data = group_data
