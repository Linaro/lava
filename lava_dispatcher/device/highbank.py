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
from lava_dispatcher.downloader import (
    download_image,
    )
from lava_dispatcher.utils import (
    logging_system,
    logging_spawn,
    mk_targz,
    rmtree,
)
from lava_dispatcher.ipmi import IPMITool


class HighbankTarget(Target):

    def __init__(self, context, config):
        super(HighbankTarget, self).__init__(context, config)
        self.proc = logging_spawn(self.config.connection_command)
        self.proc.logfile_read = context.logfile_read
        self.ipmitool = IPMITool(self.config.ecmeip)

    def deploy_linaro(self, hwpack, rfs, bootloader):
        with self._boot_master() as (runner, master_ip):
            rootfs = rfs
            kernel_deb = hwpack
            hostname = self.config.hostname
            self._format_testpartition(runner)
            runner.run('mkdir -p /mnt')
            runner.run('mount /dev/disk/by-label/rootfs /mnt')
            self._target_extract(runner, rootfs, '/mnt', 300)

            # the official snapshot appears to put everything under "binary"
#            runner.run('mv /mnt/binary/* /mnt')

            # _customize_linux assumes an image :(
            self.deployment_data = Target.ubuntu_deployment_data
            runner.run('echo \'export PS1="%s"\' >> /mnt/root/.bashrc' % self.deployment_data['TESTER_PS1'])
            runner.run('echo \'%s\' > /mnt/etc/hostname' % hostname)

            runner.run('mkdir -p /mnt/boot')
            runner.run('mount /dev/disk/by-label/boot /mnt/boot')

            runner.run('wget -O /mnt/kernel.deb  %s' % kernel_deb)

            runner.run('mount --rbind /sys /mnt/sys')
            runner.run('mount --rbind /dev /mnt/dev')
            runner.run('mount -t proc none /mnt/proc')
            runner.run('grep -v rootfs /proc/mounts > /mnt/etc/mtab')

            #os.environ['ROOT'] = '/dev/disk/by-label/rootfs'
            runner.run('ROOT=/dev/disk/by-label/rootfs chroot /mnt dpkg -i kernel.deb')
            runner.run('rm /mnt/kernel.deb')

            runner.run('sync')
            runner.run('umount /mnt/sys')
            runner.run('umount /mnt/proc')
            runner.run('umount /mnt/dev/pts')
            runner.run('umount /mnt/dev')
            runner.run('umount /mnt/boot')
            runner.run('umount /mnt')

    def power_on(self):
        self.ipmitool.set_to_boot_from_disk()
        #self.ipmitool.power_off()
        self.ipmitool.power_on()
        self.ipmitool.reset()
        return self.proc

    def power_off(self, proc):
        self.ipmitool.power_off()

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
        self.ipmitool.set_to_boot_from_pxe()
        self.ipmitool.reset()
        self.proc.expect("\(initramfs\)")
        self.proc.sendline('export PS1="%s"' % self.MASTER_PS1)
        self.proc.expect(self.MASTER_PS1_PATTERN, timeout=180, lava_no_logging=1)
        runner = HBMasterCommandRunner(self)
        runner.run(". /scripts/functions")
        ip_pat = '\d\d?\d?\.\d\d?\d?\.\d\d?\d?\.\d\d?\d?'
        runner.run("DEVICE=eth0 configure_networking", response='address: (%s)' % ip_pat)
        if runner.match_id != 0:
            msg = "Unable to determine master image IP address"
            logging.error(msg)
            raise CriticalError(msg)
        ip = runner.match.group(1)
        logging.debug("Master image IP is %s" % ip)
        try:
            yield runner, ip
        finally:
           logging.debug("deploy done")
#            self.proc.close()

    def _format_testpartition(self, runner, fstype='ext4'):
        logging.info("Formatting boot and rootfs partitions")
        runner.run('mkfs -t %s -q /dev/disk/by-label/rootfs -L rootfs'
            % fstype, timeout=1800)
        #runner.run('mkfs.vfat /dev/disk/by-label/boot -n boot')
        runner.run('mkfs -t ext2 -q /dev/disk/by-label/boot -L boot')

    def _target_extract(self, runner, tar_url, dest, timeout=-1):
        decompression_cmd = ''
        if tar_url.endswith('.gz') or tar_url.endswith('.tgz'):
            decompression_cmd = 'gunzip -c - |'
        elif tar_url.endswith('.bz2'):
            decompression_cmd = 'bunzip2 -c - |'
        else:
            raise RuntimeError('bad file extension: %s' % tar_url)

        runner.run('wget -O - %s | %s'
            'tar --warning=no-timestamp --numeric-owner -C %s -xf -'
            % (tar_url, decompression_cmd, dest),
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
