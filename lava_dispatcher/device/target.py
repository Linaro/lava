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

from lava_dispatcher.client.base import (
    wait_for_prompt
)
from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted
)
import lava_dispatcher.utils as utils
from lava_dispatcher import deployment_data


def get_target(context, device_config):
    ipath = 'lava_dispatcher.device.%s' % device_config.client_type
    m = __import__(ipath, fromlist=[ipath])
    return m.target_class(context, device_config)


class Target(object):
    """ Defines the contract needed by the dispatcher for dealing with a
    target device
    """

    def __init__(self, context, device_config):
        self.context = context
        self.config = device_config
        self.boot_options = []
        self._scratch_dir = None
        self.__deployment_data__ = None

    @property
    def deployment_data(self):
        if self.__deployment_data__:
            return self.__deployment_data__
        else:
            raise RuntimeError("No operating system deployed. "
                               "Did you forget to run a deploy action?")

    @deployment_data.setter
    def deployment_data(self, data):
        self.__deployment_data__ = data

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

    def deploy_linaro(self, hwpack, rfs, bootloadertype):
        raise NotImplementedError('deploy_image')

    def deploy_android(self, boot, system, userdata):
        raise NotImplementedError('deploy_android_image')

    def deploy_linaro_prebuilt(self, image, bootloadertype):
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
                pass

    def _get_runner(self, proc):
        from lava_dispatcher.client.base import CommandRunner
        pat = self.tester_ps1_pattern
        incrc = self.tester_ps1_includes_rc
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
                    src = os.path.join(root, file_name)
                    if name is not None:
                        dest = os.path.join(odir, name)
                        new_src = os.path.join(root, name)
                    else:
                        dest = os.path.join(odir, file_name)
                    if src != dest:
                        if name is not None:
                            shutil.copyfile(src, dest)
                            shutil.move(src, new_src)
                        else:
                            shutil.copyfile(src, dest)
                        return dest
                    else:
                        if name is not None:
                            shutil.move(src, new_src)
                        return dest
        return dest

    def _wait_for_prompt(self, connection, prompt_pattern, timeout):
        wait_for_prompt(connection, prompt_pattern, timeout)

    def _is_job_defined_boot_cmds(self, boot_cmds):
        if isinstance(self.config.boot_cmds, basestring):
            return False
        else:
            return True

    def _enter_bootloader(self, connection):
        if connection.expect(self.config.interrupt_boot_prompt) != 0:
            raise Exception("Failed to enter bootloader")
        if self.config.interrupt_boot_control_character:
            connection.sendcontrol(self.config.interrupt_boot_control_character)
        else:
            connection.send(self.config.interrupt_boot_command)

    def _customize_bootloader(self, connection, boot_cmds):
        prompt_regex = self.config.bootloader_prompt
        try_send = self.config.bootloader_prompt_test_send
        test_response_regex = self.config.bootloader_prompt_test_response
        prompt_is_re = self.config.bootloader_prompt_is_re
        wait_for_prompt(self.proc, prompt_regex, 300, try_send,
                        test_response_regex, prompt_is_re)

        cmd_number = 0
        for line in boot_cmds:
            cmd_number += 1
            parts = re.match('^(?P<action>sendline|expect|wait_for_prompt)'
                             '\s*(?P<command>.*)', line)
            if parts:
                try:
                    action = parts.group('action')
                    command = parts.group('command')
                except AttributeError as e:
                    raise Exception("Badly formatted command in \
                                      boot_cmds %s" % e)
                if action == "sendline":
                    connection.sendline(command)
                elif action == "expect":
                    command = re.escape(command)
                    connection.expect(command, timeout=300)
                elif action == "wait_for_prompt":
                    wait_for_prompt(self.proc, prompt_regex, 5, try_send,
                                    test_response_regex, prompt_is_re)
            else:
                connection.sendline(line)
                if cmd_number != len(boot_cmds):
                    # If this was the last command, don't wait for a prompt
                    # because it *should* be the boot command. If you need
                    # to wait for a prompt after the last command, insert
                    # wait_for_prompt at the end of the command list.
                    wait_for_prompt(self.proc, prompt_regex, 300, try_send,
                                    test_response_regex, prompt_is_re)

    def _target_extract(self, runner, tar_file, dest, timeout=-1):
        tmpdir = self.context.config.lava_image_tmpdir
        url = self.context.config.lava_image_url
        tar_file = tar_file.replace(tmpdir, '')
        tar_url = '/'.join(u.strip('/') for u in [url, tar_file])
        self._target_extract_url(runner, tar_url, dest, timeout=timeout)

    def _target_extract_url(self, runner, tar_url, dest, timeout=-1):
        decompression_cmd = ''
        if tar_url.endswith('.gz') or tar_url.endswith('.tgz'):
            decompression_cmd = '| /bin/gzip -dc'
        elif tar_url.endswith('.bz2'):
            decompression_cmd = '| /bin/bzip2 -dc'
        elif tar_url.endswith('.tar'):
            decompression_cmd = ''
        else:
            raise RuntimeError('bad file extension: %s' % tar_url)

        runner.run('wget -O - %s %s | /bin/tar -C %s -xmf -'
                   % (tar_url, decompression_cmd, dest),
                   timeout=timeout)

    def _start_busybox_http_server(self, runner, ip):
        runner.run('busybox httpd -f &')
        runner.run('echo $! > /tmp/httpd.pid')
        url_base = "http://%s" % ip
        return url_base

    def _stop_busybox_http_server(self, runner):
        runner.run('kill `cat /tmp/httpd.pid`')

    def _customize_prompt_hostname(self, rootdir, profile_path):
        if re.search("%s", profile_path):
            # If profile path is expecting a rootdir in it, perform string
            # substitution.
            profile_path = profile_path % rootdir

        with open(profile_path, 'a') as f:
            f.write('export PS1="%s"\n' % self.tester_ps1)
        with open('%s/etc/hostname' % rootdir, 'w') as f:
            f.write('%s\n' % self.config.hostname)

    @property
    def tester_ps1(self):
        return self._get_from_config_or_deployment_data('tester_ps1')

    @property
    def tester_ps1_pattern(self):
        return self._get_from_config_or_deployment_data('tester_ps1_pattern')

    @property
    def tester_ps1_includes_rc(self):
        # tester_ps1_includes_rc is a string so we can decode it here as
        # yes/no/ not set. If it isn't set, we stick with the device
        # default. We can't do the tri-state logic as a BoolOption because an
        # unset BoolOption returns False, not None, so we can't detect not set.
        value = self._get_from_config_or_deployment_data(
            'tester_ps1_includes_rc')

        if isinstance(value, bool):
            return value

        if value.lower() in ['y', '1', 'yes', 'on', 'true']:
           return True
        elif value.lower() in ['n', '0', 'no', 'off', 'false']:
            return False
        else:
            raise ValueError("Unable to determine boolosity of %r" % value)

    @property
    def tester_rc_cmd(self):
        return self._get_from_config_or_deployment_data('tester_rc_cmd')

    def _get_from_config_or_deployment_data(self, key):
        value = getattr(self.config, key.lower())
        if value is None:
            return self.deployment_data[key.upper()]
        else:
            return value

    def _customize_linux(self, image):
        # XXX Re-examine what to do here in light of deployment_data import.
        #perhaps make self.deployment_data = deployment_data({overrides: dict})
        #and remove the write function completely?

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

            profile_path = "%s/etc/profile"
            if os_release_id == 'debian' or os_release_id == 'ubuntu' or \
                    os.path.exists('%s/etc/debian_version' % mnt):
                self.deployment_data = deployment_data.ubuntu
                profile_path = '%s/root/.bashrc'
            elif os_release_id == 'fedora':
                self.deployment_data = deployment_data.fedora
            else:
                # assume an OE based image. This is actually pretty safe
                # because we are doing pretty standard linux stuff, just
                # just no upstart or dash assumptions
                self.deployment_data = deployment_data.oe

            self._customize_prompt_hostname(mnt, profile_path)
