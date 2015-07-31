# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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
import re
import contextlib
import logging
import subprocess

from lava_dispatcher import deployment_data
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.utils import (
    ensure_directory,
    finalize_process,
)
from lava_dispatcher.errors import (
    CriticalError,
    OperationFailed,
)


class LxcTarget(Target):

    def __init__(self, context, config):
        super(LxcTarget, self).__init__(context, config)
        self.proc = None
        self.name = None
        self.persist = None
        self._lxc_options = None

    def deploy_lxc_image(self, name, release, arch, target_type, persist):
        # Check for errors
        if release is None and arch is None:
            raise CriticalError("You must specify a release and architecture")

        try:
            subprocess.check_output(['lxc-create', '-t', 'download', '-n', name,
                                     '--', '--dist', target_type, '--release',
                                     release, '--arch', arch]).strip()
            logging.info("Container created.")
        except subprocess.CalledProcessError:
            logging.info("Container already exists.")

        logging.debug("Attempting to set deployment data")
        self.deployment_data = deployment_data.get(target_type)
        self.name = name
        self.persist = persist

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        root = '/var/lib/lxc/%s/rootfs' % self.name
        logging.debug("Accessing the file system at %s", root)
        dest = root + directory
        ensure_directory(dest)
        yield dest

    def power_on(self):
        self._check_power_state()

        logging.info("Starting lxc container %s", self.name)
        try:
            subprocess.check_output(['lxc-start', '--name', self.name,
                                     '--daemon']).strip()
            logging.info("Container %s started successfully.", self.name)
        except subprocess.CalledProcessError:
            raise CriticalError("Starting %s container failed." % self.name)

        lxc_attach_cmd = 'lxc-attach -n %s ' % self.name
        self.proc = self.context.spawn(lxc_attach_cmd, timeout=1200)
        self.proc.sendline('export PS1="%s"' % self.tester_ps1)
        logging.info("Attached to %s container." % self.name)
        return self.proc

    def power_off(self, proc):
        if self.proc:
            try:
                subprocess.check_call(['lxc-stop', '-n', self.name])
                if not self.persist:
                    subprocess.check_call(['lxc-destroy', '-n', self.name])
                    logging.info('Destroyed container %s' % self.name)
            except OperationFailed:
                logging.info('Power off failed')
        finalize_process(self.proc)
        self.proc = None

    def get_device_version(self):
        return "unknown"

    def _check_power_state(self):
        if self.proc is not None:
            logging.warning('device already powered on, powering off first')
            self.power_off(None)


target_class = LxcTarget
