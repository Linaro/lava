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
    image_partition_mounted,
)
from lava_dispatcher.ipmi import IPMITool


class HighbankTarget(Target):

    def __init__(self, context, config):
        super(HighbankTarget, self).__init__(context, config)
        self.proc = logging_spawn(self.config.connection_command)
        self.proc.logfile_read = context.logfile_read
        self.ipmitool = IPMITool(self.config.ecmeip)

        Target.android_deployment_data['boot_cmds'] = 'boot_cmds_android'
        Target.ubuntu_deployment_data['boot_cmds'] = 'boot_cmds'
        Target.oe_deployment_data['boot_cmds'] = 'boot_cmds_oe'

        # used for tarballcache logic to get proper boot_cmds
        Target.ubuntu_deployment_data['data_type'] = 'ubuntu'
        Target.oe_deployment_data['data_type'] = 'oe'
        self.target_map = {
            'android': Target.android_deployment_data,
            'oe': Target.oe_deployment_data,
            'ubuntu': Target.ubuntu_deployment_data,
            }

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
        self.deployment_data = Target.ubuntu_deployment_data
        image_file = generate_image(self, hwpack, rfs, self.scratch_dir, bootloader)    

#        # deploy as an image
#        os.system("bzip2 %s" % image_file)
#        image_file = image_file.".bz2"
#        self._deploy_image(image_file, "/dev/sda")

        # deploy as root and boot tarballs
        (boot_tgz, root_tgz, data) = self._generate_tarballs(image_file)
        self._deploy_tarballs(boot_tgz, root_tgz)

    def _deploy_image(self, image_file, device):
        with self._boot_master() as (runner, master_ip, dns):
            hostname = self.config.hostname

            tmpdir = self.context.config.lava_image_tmpdir
            url = self.context.config.lava_image_url
            image_file = image_file.replace(tmpdir, '')
            image_url = '/'.join(u.strip('/') for u in [url, image_file])

            decompression_cmd = ''
            if image_url.endswith('.gz') or image_url.endswith('.tgz'):
                decompression_cmd = '| /bin/gzip -dc'
            elif image_url.endswith('.bz2'):
                decompression_cmd = '| /bin/bzip2 -dc'

            runner.run('wget %s -O - %s | dd of=%s' % (image_url, decompression_cmd, device), timeout=1800)
            #runner.run('mkdir -p /mnt')
            #root_partition = self.get_partition(self.config.root_part)
            #runner.run('mount %s /mnt' % root_partition)
            #runner.run('umount /mnt')

            # Replace the kernel and boot.scr
            runner.run('mkdir -p /boot')
            boot_partition = self.get_partition(self.config.boot_part)
            runner.run('mount %s /boot' % boot_partition)
            runner.run('cd /boot')
            runner.run('wget http://hackbox:8100/kernel.ubuntu.tar.gz -O - | /bin/gzip -dc | /bin/tar -xf -')
            runner.run('cd /')
            runner.run('umount /boot')

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

            runner.run('cd /mnt/boot')
            runner.run('wget http://hackbox:8100/kernel.ubuntu.tar.gz -O - | /bin/gzip -dc | /bin/tar -xf -')
            runner.run('cd /')

            runner.run('umount /mnt/boot')
            runner.run('umount /mnt')

    def _generate_tarballs(self, image_file):
        self._customize_linux(image_file)
        boot_tgz = os.path.join(self.scratch_dir, "boot.tgz")
        root_tgz = os.path.join(self.scratch_dir, "root.tgz")
        try:
            self._extract_partition(image_file, self.config.boot_part, boot_tgz)
            self._extract_partition(image_file, self.config.root_part, root_tgz)
        except:
            logging.exception("Failed to generate tarballs")
            raise

        # we need to associate the deployment data with these so that we
        # can provide the proper boot_cmds later on in the job
        data = self.deployment_data['data_type']
        return boot_tgz, root_tgz, data

    def _extract_partition(self, image, partno, tarfile):
        """Mount a partition and produce a tarball of it

        :param image: The image to mount
        :param partno: The index of the partition in the image
        :param tarfile: path and filename of the tgz to output
        """
        with image_partition_mounted(image, partno) as mntdir:
            mk_targz(tarfile, mntdir, asroot=True)


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
            runner.run('mkdir -p /mnt')
            partition = self.get_partition(partition)
            runner.run('mount %s /mnt' % partition)
            try:
                targetdir = '/mnt/%s' % directory
                if not runner.is_file_exist(targetdir):
                    runner.run('mkdir -p %s' % targetdir)

                parent_dir, target_name = os.path.split(targetdir)

                # Start httpd on the target
                runner.run('/bin/tar -cmzf /tmp/fs.tgz -C %s %s' % (parent_dir, target_name))
                runner.run('cd /tmp')  # need to be in same dir as fs.tgz
                runner.run('busybox httpd -v')   # busybox produces no output to parse for, so let it run as a daemon
                port = 80
                
                url = "http://%s:%s/fs.tgz" % (master_ip, port)
                logging.info("Fetching url: %s" % url)
                tf = download_with_retry(self.context, self.scratch_dir, url, False)

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
                    self._target_extract(runner, tf, parent_dir)

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

    def _create_testpartitions(self, runner, device='/dev/sda'):
        logging.info("Partitioning the disk")
        runner.run('parted %s --script mklabel msdos' % device)
        runner.run('parted %s --script mkpart primary ext2 1049kB 99.6MB' % device)
        runner.run('parted %s --script mkpart primary ext4 99.6MB 16GB' % device)
        runner.run('parted %s --script mkpart primary linux-swap 16GB 24GB' % device)
        runner.run('parted %s --script set 1 boot on' % device)
        runner.run('parted %s --script p' % device)


    def _format_testpartitions(self, runner, rootfstype='ext4', bootfstype='ext2',
                                             rootfsname="rootfs", bootfsname="boot"):
        logging.info("Formatting rootfs partition")
        root_partition_device = "/dev/sda2"
        boot_partition_device = "/dev/sda1"
        runner.run('mkfs -t %s -q %s -L %s'
            % (rootfstype,root_partition_device, rootfsname), timeout=1800)
        logging.info("Formatting boot partition")
        runner.run('mkfs -t %s -q %s -L %s'
            % (bootfstype, boot_partition_device, bootfsname), timeout=1800)

    def _target_extract(self, runner, tar_file, dest, timeout=-1):
        tmpdir = self.context.config.lava_image_tmpdir
        url = self.context.config.lava_image_url
        tar_file = tar_file.replace(tmpdir, '')
        tar_url = '/'.join(u.strip('/') for u in [url, tar_file])
        self._target_extract_url(runner,tar_url,dest,timeout=timeout)

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

