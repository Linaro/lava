# Copyright (C) 2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
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
import os
import shutil
import re

from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted)
import lava_dispatcher.utils as utils


def get_target(context, device_config):
    ipath = 'lava_dispatcher.device.%s' % device_config.client_type
    m = __import__(ipath, fromlist=[ipath])
    return m.target_class(context, device_config)


class Target(object):
    """ Defines the contract needed by the dispatcher for dealing with a
    target device
    """

    ANDROID_TESTER_PS1 = "root@linaro# "

    # The target deployment functions will point self.deployment_data to
    # the appropriate dictionary below. Code such as actions can contribute
    # to these structures with special handling logic
    android_deployment_data = {
        'TESTER_PS1': ANDROID_TESTER_PS1,
        'TESTER_PS1_PATTERN': ANDROID_TESTER_PS1,
        'TESTER_PS1_INCLUDES_RC': False,
    }
    ubuntu_deployment_data = {
        'TESTER_PS1': "linaro-test [rc=$(echo \$?)]# ",
        'TESTER_PS1_PATTERN': "linaro-test \[rc=(\d+)\]# ",
        'TESTER_PS1_INCLUDES_RC': True,
    }
    oe_deployment_data = {
        'TESTER_PS1': "linaro-test [rc=$(echo \$?)]# ",
        'TESTER_PS1_PATTERN': "linaro-test \[rc=(\d+)\]# ",
        'TESTER_PS1_INCLUDES_RC': True,
    }
    fedora_deployment_data = {
        'TESTER_PS1': "linaro-test [rc=$(echo \$?)]# ",
        'TESTER_PS1_PATTERN': "linaro-test \[rc=(\d+)\]# ",
        'TESTER_PS1_INCLUDES_RC': True,
    }

    def __init__(self, context, device_config):
        self.context = context
        self.config = device_config
        self.boot_options = []
        self._scratch_dir = None
        self.deployment_data = {}

    @property
    def scratch_dir(self):
        if self._scratch_dir is None:
            self._scratch_dir = utils.mkdtemp(
                self.context.config.lava_image_tmpdir)
        return self._scratch_dir

    def power_on(self):
        """ responsible for powering on the target device and returning an
        instance of a pexpect session
        """
        raise NotImplementedError('power_on')

    def deploy_linaro(self, hwpack, rfs, bootloader):
        raise NotImplementedError('deploy_image')

    def deploy_android(self, boot, system, userdata):
        raise NotImplementedError('deploy_android_image')

    def deploy_linaro_prebuilt(self, image):
        raise NotImplementedError('deploy_linaro_prebuilt')

    def power_off(self, proc):
        if proc is not None:
            proc.close()

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        """ Allows the caller to interact directly with a directory on
        the target. This method yields a directory where the caller can
        interact from. Upon the exit of this context, the changes will be
        applied to the target.

        The partition parameter refers to partition number the directory
        would reside in as created by linaro-media-create. ie - the boot
        partition would be 1. In the case of something like the master
        image, the target implementation must map this number to the actual
        partition its using.

        NOTE: due to difference in target implementations, the caller should
        try and interact with the smallest directory locations possible.
        """
        raise NotImplementedError('file_system')

    def extract_tarball(self, tarball_url, partition, directory='/'):
        """ This is similar to the file_system API but is optimized for the
        scenario when you just need explode a potentially large tarball on
        the target device. The file_system API isn't really suitable for this
        when thinking about an implementation like master.py
        """
        raise NotImplementedError('extract_tarball')

    @contextlib.contextmanager
    def runner(self):
        """ Powers on the target, returning a CommandRunner object and will
        power off the target when the context is exited
        """
        self.proc = runner = None
        try:
            self.proc = self.power_on()
            runner = self._get_runner(self.proc)
            yield runner
        finally:
            if self.proc and runner:
                self.power_off(self.proc)

    def _get_runner(self, proc):
        from lava_dispatcher.client.base import CommandRunner
        pat = self.deployment_data['TESTER_PS1_PATTERN']
        incrc = self.deployment_data['TESTER_PS1_INCLUDES_RC']
        return CommandRunner(proc, pat, incrc)

    def get_test_data_attachments(self):
        return []

    def get_device_version(self):
        """ Returns the device version associated with the device, i.e. version
        of emulation software, or version of master image. Must be overriden in
        subclasses.
        """
        return 'unknown'

    def _find_and_copy(self, rootdir, odir, pattern, name=None):
        dest = None
        for root, dirs, files in os.walk(rootdir):
            for file_name in files:
                if re.match(pattern, file_name):
                    if name:
                        dest = os.path.join(odir, name)
                    else:
                        dest = os.path.join(odir, file_name)
                    if rootdir != odir:
                        src = os.path.join(root, file_name)
                        shutil.copyfile(src, dest)
                        return dest
                    else:
                        return dest
        return dest

    def _customize_bootloader(self):
        self.proc.expect(self.config.bootloader_prompt, timeout=300)
        if isinstance(self.config.boot_cmds, basestring):
            boot_cmds = utils.string_to_list(self.config.boot_cmds.encode('ascii'))
        else:
            boot_cmds = self.config.boot_cmds
        for line in boot_cmds:
            parts = re.match('^(?P<action>sendline|expect)\s*(?P<command>.*)', line)
            if parts:
                try:
                    action = parts.group('action')
                    command = parts.group('command')
                except AttributeError as e:
                    raise Exception("Badly formatted command in boot_cmds %s" % e)
                if action == "sendline":
                    self.proc.send(command)
                    self.proc.sendline('')
                elif action == "expect":
                    command = re.escape(command)
                    self.proc.expect(command, timeout=300)
            else:
                self.proc.sendline(line)

    def _customize_ubuntu(self, rootdir):
        self.deployment_data = Target.ubuntu_deployment_data
        with open('%s/root/.bashrc' % rootdir, 'a') as f:
            f.write('export PS1="%s"\n' % self.deployment_data['TESTER_PS1'])
        with open('%s/etc/hostname' % rootdir, 'w') as f:
            f.write('%s\n' % self.config.hostname)

    def _customize_oe(self, rootdir):
        self.deployment_data = Target.oe_deployment_data
        with open('%s/etc/profile' % rootdir, 'a') as f:
            f.write('export PS1="%s"\n' % self.deployment_data['TESTER_PS1'])
        with open('%s/etc/hostname' % rootdir, 'w') as f:
            f.write('%s\n' % self.config.hostname)

    def _customize_fedora(self, rootdir):
        self.deployment_data = Target.fedora_deployment_data
        with open('%s/etc/profile' % rootdir, 'a') as f:
            f.write('export PS1="%s"\n' % self.deployment_data['TESTER_PS1'])
        with open('%s/etc/hostname' % rootdir, 'w') as f:
            f.write('%s\n' % self.config.hostname)

    def _customize_linux(self, image):
        root_part = self.config.root_part
        os_release_id = 'linux'
        with image_partition_mounted(image, root_part) as mnt:
            os_release_file = '%s/etc/os-release' % mnt
            if os.path.exists(os_release_file):
                for line in open(os_release_file):
                    if line.startswith('ID='):
                        os_release_id = line[(len('ID=')):]
                        os_release_id = os_release_id.strip('\"\n')
                        break

            if os_release_id == 'debian' or os_release_id == 'ubuntu' or \
                    os.path.exists('%s/etc/debian_version' % mnt):
                self._customize_ubuntu(mnt)
            elif os_release_id == 'fedora':
                self._customize_fedora(mnt)
            else:
                # assume an OE based image. This is actually pretty safe
                # because we are doing pretty standard linux stuff, just
                # just no upstart or dash assumptions
                self._customize_oe(mnt)
