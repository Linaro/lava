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
import re

from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted,
    )
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

    def deploy_linaro(self, hwpack, rfs):
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
        proc = runner = None
        try:
            proc = self.power_on()
            runner = self._get_runner(proc)
            yield runner
        finally:
            if proc and runner:
                self.power_off(proc)

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

    def _rewrite_partition_number(self, matchobj):
        """ Returns the partition number after rewriting it to n+2.
        """
        partition = int(matchobj.group('partition')) + 2
        return matchobj.group(0)[:2] + ':' + str(partition) + ' '

    def _rewrite_boot_cmds(self, boot_cmds):
        """
        Returns boot_cmds list after rewriting things such as:
        
        partition number from n to n+2
        root=LABEL=testrootfs instead of root=UUID=ab34-...
        """
        boot_cmds = re.sub(
            r"root=UUID=\S+", "root=LABEL=testrootfs", boot_cmds, re.MULTILINE)
        pattern = "\s+\d+:(?P<partition>\d+)\s+"
        boot_cmds = re.sub(
            pattern, self._rewrite_partition_number, boot_cmds, re.MULTILINE)
        
        return boot_cmds.split('\n')

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

    def _customize_linux(self, image):
        root_part = self.config.root_part
        boot_part = self.config.boot_part

        with image_partition_mounted(image, root_part) as mnt:
            if os.path.exists('%s/etc/debian_version' % mnt):
                self._customize_ubuntu(mnt)
            else:
                # assume an OE based image. This is actually pretty safe
                # because we are doing pretty standard linux stuff, just
                # just no upstart or dash assumptions
                self._customize_oe(mnt)

        # Read boot.txt from the boot partition of image.
        with image_partition_mounted(image, boot_part) as mnt:
            if os.path.exists('%s/boot.txt' % mnt):
                with open('%s/boot.txt' % mnt, 'r') as f:
                    boot_cmds = self._rewrite_boot_cmds(f.read())
                self.deployment_data['boot_cmds_dynamic'] = boot_cmds
