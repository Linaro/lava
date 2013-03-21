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
    download_with_retry,
    )
from lava_dispatcher.utils import (
    logging_system,
    logging_spawn,
    mk_targz,
    rmtree,
)
from lava_dispatcher.client.lmc_utils import (
    generate_image,
)
from lava_dispatcher.ipmi import IPMITool


class HighbankTarget(Target):

    def __init__(self, context, config):
        super(HighbankTarget, self).__init__(context, config)
        self.proc = logging_spawn(self.config.connection_command)
        self.proc.logfile_read = context.logfile_read
        self.ipmitool = IPMITool(self.config.ecmeip)

    def get_device_version(self):
        return 'unknown'

    def power_on(self):
        self.ipmitool.set_to_boot_from_disk()
        self.ipmitool.power_on()
        self.ipmitool.reset()
        return self.proc

    def power_off(self, proc):
        self.ipmitool.power_off()

    def deploy_linaro(self, hwpack, rfs, bootloader):
#        image_file = generate_image(self, hwpack, rfs, self.scratch_dir, bootloader)    
#        (boot_tgz, root_tgz, data) = self._generate_tarballs(image_file)

        # map hwpack & rfs for ubuntu tarball (temporary)
        boot_tgz = hwpack
        root_tgz = rfs

        self.deployment_data = Target.ubuntu_deployment_data
        self._deploy_tarball_images(boot_tgz, root_tgz)

    def _deploy_tarballs(self, bootfs, rootfs):
        with self._boot_master() as (runner, master_ip, dns):
            hostname = self.config.hostname
            self._create_testpartitions(runner)
            self._format_testpartitions(runner)

            runner.run('mkdir -p /mnt')
            root_partition = self.get_partition(self.config.root_part)
            runner.run('mount %s /mnt' % root_partition)
            
            self._target_extract(runner, rootfs, '/mnt')

            runner.run('mkdir -p /mnt/boot')
            boot_partition = self.get_partition(self.config.boot_part)
            runner.run('mount %s /mnt/boot' % boot_partition)

            self._target_extract(runner, bootfs, '/mnt')

            runner.run('umount /mnt/boot')
            runner.run('umount /mnt')

    def _generate_tarballs(self, image_file):
        self._customize_linux(image_file)
        boot_tgz = os.path.join(self.scratch_dir, "boot.tgz")
        root_tgz = os.path.join(self.scratch_dir, "root.tgz")
        try:
            _extract_partition(image_file, self.config.boot_part, boot_tgz)
            _extract_partition(image_file, self.config.root_part, root_tgz)
        except:
            logging.exception("Failed to generate tarballs")
            raise

        # we need to associate the deployment data with these so that we
        # can provide the proper boot_cmds later on in the job
        data = self.deployment_data['data_type']
        return boot_tgz, root_tgz, data

    def get_partition(self, partition):
        if partition == self.config.boot_part:
            partition = '/dev/disk/by-label/boot'
        elif partition == self.config.root_part:
            partition = '/dev/disk/by-label/rootfs'
        else:
            XXX
        return partition


    @contextlib.contextmanager
    def file_system(self, partition, directory):
        logging.info('attempting to access master filesystem %r:%s' %
            (partition, directory))

        assert directory != '/', "cannot mount entire partition"

        with self._boot_master() as (runner, master_ip, dns):
            if not runner.is_file_exist("/mnt"):
                runner.run('mkdir -p /mnt')
            partition = self.get_partition(partition)
            runner.run('mount %s /mnt' % partition)
            try:
                targetdir = '/mnt/%s' % directory
                if not runner.is_file_exist(targetdir):
                    runner.run('mkdir -p %s' % targetdir)

                parent_dir, target_name = os.path.split(targetdir)

                # Start httpd on the target
                runner.run('/bin/tar -czf /tmp/fs.tgz -C %s %s' %
                    (parent_dir, target_name))
                runner.run('cd /tmp')  # need to be in same dir as fs.tgz
                runner.run('busybox httpd -v')   # busybox produces no output to parse for, so let it run as a daemon
                port = 80
                
                url = "http://%s:%s/fs.tgz" % (master_ip, port)
                logging.info("Fetching url: %s" % url)
                tf = download_with_retry(
                    self.context, self.scratch_dir, url, False)

                tfdir = os.path.join(self.scratch_dir, str(time.time()))

                try:
                    os.mkdir(tfdir)
                    logging_system('/bin/tar -C %s -xzf %s' % (tfdir, tf))
                    yield os.path.join(tfdir, target_name)

                finally:
                    tf = os.path.join(self.scratch_dir, 'fs.tgz')
                    mk_targz(tf, tfdir)
                    rmtree(tfdir)

                    # get the last 2 parts of tf, ie "scratchdir/tf.tgz"
                    tf = '/'.join(tf.split('/')[-2:])
                    url = '%s/%s' % (self.context.config.lava_image_url, tf)
                    runner.run('rm -rf %s' % targetdir)
                    self._target_extract(runner, url, parent_dir)

            finally:
                    runner.run('killall busybox')
                    runner.run('umount /mnt')

    MASTER_PS1 = 'root@master# '
    MASTER_PS1_PATTERN = 'root@master# '

    @contextlib.contextmanager
    def _boot_master(self):
        self.ipmitool.set_to_boot_from_pxe()
        self.ipmitool.power_on()
        self.ipmitool.reset()

        # Two reboots seem to be necessary to ensure that pxe boot is used.
        # Need to identify the cause and fix it
        self.proc.expect("Hit any key to stop autoboot:")
        self.proc.sendline('')
        self.ipmitool.set_to_boot_from_pxe()
        self.ipmitool.reset()

        self.proc.expect("\(initramfs\)")
        self.proc.sendline('export PS1="%s"' % self.MASTER_PS1)
        self.proc.expect(self.MASTER_PS1_PATTERN, timeout=180, lava_no_logging=1)
        runner = HBMasterCommandRunner(self)
        runner.run(". /scripts/functions")
        ip_pat = '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        device = "eth0"
        runner.run("DEVICE=%s configure_networking" % device, response='address: (%s) ' % ip_pat, wait_prompt=False)
        if runner.match_id != 0:
            msg = "Unable to determine master image IP address"
            logging.error(msg) 
            raise CriticalError(msg)
        ip = runner.match.group(1)
        logging.debug("Target IP address = %s" % ip)

        runner.run("ipconfig %s" % device, response='dns0     : (%s)' % ip_pat, wait_prompt=False)
        if runner.match_id != 0:
            msg = "Unable to determine dns address"
            logging.error(msg) 
            raise CriticalError(msg)
        dns = runner.match.group(1)
        logging.info("DNS Address is %s" % dns)
        runner.run("echo nameserver %s > /etc/resolv.conf" % dns)

        try:
            yield runner, ip, dns
        finally:
           logging.debug("deploy done")

    def _create_testpartitions(self, runner):
        logging.info("Partitioning the disk")
        runner.run('parted --script mklabel gpt')
        runner.run('parted --script mkpart primary ext2 1049kB 99.6MB')
        runner.run('parted --script mkpart primary ext4 99.6MB 16GB')
        runner.run('parted --script mkpart primary linux-swap 16GB 24GB')
        runner.run('parted --script set 1 boot on')
        runner.run('parted --script p')


    def _format_testpartitions(self, runner, rootfstype='ext4', bootfstype='ext2',
                                             rootfsname="rootfs", bootfsname="bootfs"):
        logging.info("Formatting rootfs partition")
        root_partition_device = "/dev/sda2"
        boot_partition_device = "/dev/sda1"
        runner.run('mkfs -t %s -q %s -L %s'
            % (fstype,root_partition_device, rootfsname), timeout=1800)
        logging.info("Formatting boot partition")
        runner.run('mkfs -t %s -q %s -L %s'
            % (bootfstype, boot_partition_device, bootfsname), timeout=1800)

    def _target_extract(self, runner, tar_url, dest, timeout=-1):
        decompression_cmd = ''
        if tar_url.endswith('.gz') or tar_url.endswith('.tgz'):
            decompression_cmd = 'z'
        elif tar_url.endswith('.bz2'):
            decompression_cmd = 'j'
        else:
            raise RuntimeError('bad file extension: %s' % tar_url)

        runner.run('wget -O - %s | /bin/tar -C %s -x%sf -'
            % (tar_url, dest, decompression_cmd),
            timeout=timeout)


target_class = HighbankTarget


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

