# Copyright (C) 2012 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import contextlib
import logging
import os
import pexpect
import time

from lava_dispatcher.client.base import (
    NetworkCommandRunner,
)
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.errors import (
    CriticalError,
    OperationFailed,
)
from lava_dispatcher.utils import (
    download_image,
    logging_system,
    logging_spawn,
    mk_targz,
    rmtree,
)


class HighbankTarget(Target):

    def __init__(self, context, config):
        super(HighbankTarget, self).__init__(context, config)
        self.proc = logging_spawn(self.config.connection_command)
        self.proc.logfile_read = context.logfile_read

    def deploy_linaro(self, hwpack, rfs, bootloader):
        with self._boot_master() as (runner, master_ip):
            rootfs = download_image(rfs, self.context, decompress=False)
            kernel_deb = download_image(hwpack, self.context, decompress=False)
            self._format_testpartition(runner)
            runner.run('mount /dev/sda2 /mnt')
            self._target_extract(runner, rootfs, '/mnt')
            # _customize_linux assumes an image :(
            self.deployment_data = Target.ubuntu_deployment_data
            runner.run('echo \'export PS1="%s"\' >> /mnt/root/.bashrc' % self.deployment_data['TESTER_PS1'])
            runner.run('echo \'%s\' > /mnt/etc/hostname')

            runner.run('mount /dev/sda1 /mnt/boot')
            runner.run(
                'wget --no-check-certificate --no-proxy '
                '--connect-timeout=30 -S --progress=dot -e dotbytes=2M '
                '-O /mnt/kernel.deb  %s' % kernel_deb)
            runner.run('chroot /mnt dpkg -i kernel.deb')
            runner.run('rm /mnt/kernel.deb')
            runner.run('umount /dev/sda1')
            runner.run('umount /dev/sda2')

    def power_on(self):
        self._ipmi("chassis bootdev disk")
        self._ipmi("chassis power off")
        self._ipmi("chassis power on")
        return self.proc

    def power_off(self, proc):
        self._ipmi("chassis power off")

    def get_partition(self, partition):
        if partition == self.config.boot_part:
            partition = '/dev/disk/by-label/testboot'
        elif partition == self.config.root_part:
            partition = '/dev/disk/by-label/testrootfs'
        else:
            XXX

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        logging.info('attempting to access master filesystem %r:%s' %
            (partition, directory))

        assert directory != '/', "cannot mount entire partition"

        with self._boot_master() as (runner, master_ip):
            partition = self.get_partition(partition)
            runner.run('mount %s /mnt' % partition)
            try:
                targetdir = '/mnt/%s' % directory
                if not runner.is_file_exist(targetdir):
                    runner.run('mkdir %s' % targetdir)

                parent_dir, target_name = os.path.split(targetdir)
                runner.run('tar -czf - -C %s %s | nc -l 3000' %
                    (parent_dir, target_name), wait_prompt=False)
                tf = os.path.join(self.scratch_dir, 'fs.tgz')
                logging_system('nc %s 3000 > %s' % (master_ip, tf))

                tfdir = os.path.join(self.scratch_dir, str(time.time()))
                try:
                    os.mkdir(tfdir)
                    logging_system('tar -C %s -xzf %s' % (tfdir, tf))
                    yield os.path.join(tfdir, target_name)

                finally:
                    mk_targz(tf, tfdir)
                    rmtree(tfdir)

                    # get the last 2 parts of tf, ie "scratchdir/tf.tgz"
                    tf = '/'.join(tf.split('/')[-2:])
                    url = '%s/%s' % (self.context.config.lava_image_url, tf)
                    runner.run('rm -rf %s' % targetdir)
                    self.target_extract(runner, url, parent_dir)

            finally:
                    self.proc.sendcontrol('c')  # kill SimpleHTTPServer
                    runner.run('umount /mnt')

    def get_device_version(self):
        return 'unknown'

    MASTER_PS1 = 'root@master# '
    MASTER_PS1_PATTERN = 'root@master# '

    @contextlib.contextmanager
    def _boot_master(self):
        proc = logging_spawn(self.config.connection_command)
        self._ipmi("chassis bootdev pxe")
        self._ipmi("chassis power off")
        self._ipmi("chassis power on")
        proc.expect("\(initramfs\)")
        proc.sendline('export PS1="%s"' % self.MASTER_PS1)
        proc.expect(self.MASTER_PS1_PATTERN, timeout=120, lava_no_logging=1)
        runner = HBMasterCommandRunner(self)
        runner.run(". /scripts/functions")
        ip_pat = '\d\d?\d?\.\d\d?\d?\.\d\d?\d?\.\d\d?\d?'
        runner.run("DEVICE=eth0 configure_networking", response='address: (%s)' % ip_pat)
        if runner.match_id != 0:
            msg = "Unable to determine master image IP address"
            logging.error(msg)
            raise CriticalError(msg)
        ip = self.match.group(1)
        logging.debug("Master image IP is %s" % ip)
        try:
            yield runner, ip
        finally:
            proc.close()

    def _ipmi(self, cmd):
        logging_system(
            "ipmitool -H %(ecmeip)s -U admin -P admin " % (self.config.ecmeip,)
            + cmd)

    def _format_testpartition(self, runner, fstype='ext4'):
        logging.info("Formatting boot and rootfs partitions")
        runner.run('mkfs -t %s -q /dev/disk/by-label/rootfs -L rootfs'
            % fstype, timeout=1800)
        runner.run('mkfs.vfat /dev/disk/by-label/boot -n boot')

    def _target_extract(self, runner, tar_url, dest, timeout=-1):
        decompression_char = ''
        if tar_url.endswith('.gz') or tar_url.endswith('.tgz'):
            decompression_char = 'z'
        elif tar_url.endswith('.bz2'):
            decompression_char = 'j'
        else:
            raise RuntimeError('bad file extension: %s' % tar_url)

        runner.run(
            'wget --no-check-certificate --no-proxy '
            '--connect-timeout=30 -S --progress=dot -e dotbytes=2M '
            '-O- %s | '
            'tar --warning=no-timestamp --numeric-owner -C %s -x%sf -'
            % (tar_url, dest, decompression_char),
            timeout=timeout)


class HBMasterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the master image.
    """
    def __init__(self, target):
        super(HBMasterCommandRunner, self).__init__(
            target, target.MASTER_PS1_PATTERN, prompt_str_includes_rc=False)

    def get_master_ip(self):

        pattern1 = "<(\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?)>"
        cmd = ("ifconfig %s | grep 'inet addr' | awk -F: '{print $2}' |"
                "awk '{print \"<\" $1 \">\"}'" %
                self._client.config.default_network_interface)
        self.run(
            cmd, [pattern1, pexpect.EOF, pexpect.TIMEOUT], timeout=5)
        if self.match_id != 0:
            msg = "Unable to determine master image IP address"
            logging.error(msg)
            raise CriticalError(msg)

        ip = self.match.group(1)
        logging.debug("Master image IP is %s" % ip)
        return ip

    def run(self, cmd, response=None, timeout=-1, failok=False, wait_prompt=True):
        NetworkCommandRunner.run(self, cmd, response, timeout, failok, wait_prompt)
        rc = None
        if wait_prompt:
            match_id, match = self.match_id, self.match
            NetworkCommandRunner.run(self, "echo x$?x", response='x([0-9]+)x', timeout=5)
            if self.match_id != 0:
                raise OperationFailed("")
            else:
                rc = int(self.match.group(1))
                if not failok and rc != 0:
                    raise OperationFailed(
                        "executing %r failed with code %s" % (cmd, rc))
        return rc

    def is_file_exist(self, path):
        cmd = 'ls %s > /dev/null' % path
        rc = self.run(cmd, failok=True)
        if rc == 0:
            return True
        return False


target_class = HighbankTarget
