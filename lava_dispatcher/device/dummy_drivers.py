# Copyright (C) 2013 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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


from contextlib import contextmanager
import logging
import os
import shutil
import subprocess
import time

from lava_dispatcher.errors import (
    CriticalError,
)
from lava_dispatcher.utils import finalize_process


class BaseDriver(object):

    def __init__(self, device):
        self.device = device
        self.context = device.context
        self.config = device.config

    @contextmanager
    def root(self):
        """
        """
        raise NotImplementedError("root")

    def connect(self):
        """
        """
        raise NotImplementedError("connect")

    def finalize(self, proc):
        finalize_process(proc)


class schroot(BaseDriver):

    def __init__(self, device):
        super(schroot, self).__init__(device)
        self.__session__ = None
        self.__root__ = None
        self.__chroot__ = self.config.dummy_schroot_chroot

    @property
    def session(self):
        if self.__session__ is None:
            chroot = self.__chroot__
            session_id = subprocess.check_output(['schroot', '--begin-session',
                                                  '--chroot',
                                                  chroot]).strip()
            self.__session__ = 'session:' + session_id
            logging.info("schroot session created with id %s",
                         self.__session__)

        return self.__session__

    @contextmanager
    def root(self):
        if self.__root__ is None:
            self.__root__ = subprocess.check_output(['schroot', '--location',
                                                     '--chroot',
                                                     self.session]).strip()

        yield self.__root__

    def connect(self):
        logging.info("Running schroot session %s", self.session)
        cmd = 'schroot --run-session --chroot %s' % self.session
        proc = self.context.spawn(cmd, timeout=1200)
        return proc

    def finalize(self, proc):
        logging.info("Finalizing schroot session %s", self.session)
        subprocess.check_call(['schroot', '--end-session', '--chroot',
                               self.session])


class host(BaseDriver):

    @contextmanager
    def root(self):
        yield '/'

    def connect(self):
        return self.context.spawn('bash')


class ssh(BaseDriver):

    def __init__(self, device):
        super(ssh, self).__init__(device)
        config = self.config
        if config.dummy_ssh_host is None or \
           config.dummy_ssh_identity_file is None:
            raise CriticalError('Device config requires "dummy_ssh_host" and "dummy_ssh_identity_file"!')

        self.__host__ = config.dummy_ssh_host
        self.__username__ = config.dummy_ssh_username
        self.__port__ = config.dummy_ssh_port
        self.__identity_file__ = config.dummy_ssh_identity_file

        self.__ssh_config__ = None

    @contextmanager
    def root(self):
        mount_point = os.path.join(self.device.scratch_dir, self.__host__)
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)
        subprocess.check_call([
            'sshfs',
            '%s:/' % self.__host__,
            mount_point,
            '-F', self.ssh_config,
        ])
        try:
            yield mount_point
        finally:
            subprocess.check_call(['fusermount', '-u', mount_point])

    def connect(self):
        proc = self.context.spawn('ssh -F %s %s' % (self.ssh_config,
                                                    self.__host__))
        time.sleep(5)
        return proc

    @property
    def ssh_config(self):
        if self.__ssh_config__ is None:
            base = self.device.scratch_dir
            filename = os.path.join(base, self.__host__ + '_ssh_config')

            # ssh requires the identity file to be 0600 and we can't assume the
            # one pointed by the actual configuration to be OK
            identity_file = os.path.join(base, self.__host__ + '_key')
            shutil.copyfile(self.__identity_file__, identity_file)
            os.chmod(identity_file, 0600)

            with open(filename, 'w') as f:
                f.write("User %s\n" % self.__username__)
                f.write("Port %d\n" % self.__port__)
                f.write("PasswordAuthentication no\n")
                f.write("StrictHostKeyChecking no\n")
                f.write("IdentityFile %s\n" % identity_file)
            self.__ssh_config__ = filename

            logging.debug("SSH configuration in use: \n" + open(filename).read())

        return self.__ssh_config__


class lxc(BaseDriver):

    def __init__(self, device):
        super(lxc, self).__init__(device)
        self.__session__ = None
        self.__root__ = None
        self.container = self.config.dummy_lxc_container

    @property
    def session(self):
        if self.__session__ is None:
            try:
                session_id = subprocess.check_output(['lxc-create',
                                                      '-t download',
                                                      '-n',
                                                      self.container,
                                                      '--',
                                                      '--dist',
                                                      'debian',
                                                      '--release',
                                                      'jessie',
                                                      '--arch',
                                                      'amd64']).strip()
            except subprocess.CalledProcessError:
                session_id = subprocess.check_output(['lxc-start',
                                                      '-n',
                                                      self.container,
                                                      '-d']).strip()
            self.__session__ = 'session:' + session_id
            logging.info("lxc session created with id %s",
                         self.__session__)

        return self.__session__

    @contextmanager
    def root(self):
        yield '/'

    def connect(self):
        logging.info("Running lxc session %s", self.session)
        cmd = 'lxc-attach -n %s ' % self.container
        proc = self.context.spawn(cmd, timeout=1200)
        return proc

    def finalize(self, proc):
        logging.info("Finalizing lxc session %s", self.session)
        subprocess.check_call(['lxc-stop', '-n', self.container])
