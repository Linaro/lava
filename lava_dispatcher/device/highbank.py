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

from lava_dispatcher import tarballcache

from lava_dispatcher.client.base import (
    NetworkCommandRunner,
)
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.errors import (
    NetworkError,
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

    MASTER_PS1 = 'root@master [rc=$(echo \$?)]# '
    MASTER_PS1_PATTERN = 'root@master \[rc=(\d+)\]# '

    def __init__(self, context, config):
        super(HighbankTarget, self).__init__(context, config)
        self.proc = logging_spawn(self.config.connection_command)
        self.proc.logfile_read = context.logfile_read
        self.device_version = None
        self.bootcontrol = IpmiPxeBoot(self.config.ecmeip)

    def get_device_version(self):
        return self.device_version

    def power_on(self):
        self.bootcontrol.power_on_boot_image()
        return self.proc

    def power_off(self, proc):
        self.bootcontrol.power_off()

    def deploy_linaro(self, hwpack, rfs, bootloader):
        self.deployment_data = Target.ubuntu_deployment_data
        image_file = generate_image(self, hwpack, rfs, self.scratch_dir, bootloader,
                                    extra_boot_args='1', image_size='1G')
        self._customize_linux(image_file)
        self._deploy_image(image_file, '/dev/sda')

    def deploy_linaro_prebuilt(self, image):
        self.deployment_data = Target.ubuntu_deployment_data
        image_file = download_image(image, self.context, self.scratch_dir)
        self._customize_linux(image_file)
        self._deploy_image(image_file, '/dev/sda')

    def _deploy_image(self, image_file, device):
        with self._as_master() as runner:

            # compress the image to reduce the transfer size
	    if not image_file.endswith('.bz2') and not image_file.endswith('gz'):
                os.system('bzip2 -v ' + image_file)
                image_file += '.bz2'

            tmpdir = self.context.config.lava_image_tmpdir
            url = self.context.config.lava_image_url
            image_file = image_file.replace(tmpdir, '')
            image_url = '/'.join(u.strip('/') for u in [url, image_file])

            decompression_cmd = ''
            if image_url.endswith('.gz') or image_url.endswith('.tgz'):
                decompression_cmd = '| /bin/gzip -dc'
            elif image_url.endswith('.bz2'):
                decompression_cmd = '| /bin/bzip2 -dc'

            runner.run('mkdir /builddir')
            runner.run('mount -t tmpfs -o size=4G tmpfs builddir')
            image = '/builddir/lava.img'
            runner.run('wget -O - %s %s > %s' % (image_url, decompression_cmd, image), timeout=1800)
            runner.run('dd bs=4M if=%s of=%s' % (image, device), timeout=1800)
            runner.run('umount /builddir')

    def get_partition(self, runner, partition):
        if partition == self.config.boot_part:
            partition = '/dev/disk/by-label/boot'
        elif partition == self.config.root_part:
            partition = '/dev/disk/by-label/rootfs'
        else:
            raise RuntimeError(
                'unknown master image partition(%d)' % partition)
        return partition


    @contextlib.contextmanager
    def file_system(self, partition, directory):
        logging.info('attempting to access master filesystem %r:%s' %
            (partition, directory))

        assert directory != '/', "cannot mount entire partition"

        with self._as_master() as runner:
            runner.run('mkdir -p /mnt')
            partition = self.get_partition(runner, partition)
            runner.run('mount %s /mnt' % partition)
            try:
                targetdir = '/mnt/%s' % directory
                runner.run('mkdir -p %s' % targetdir)

                parent_dir, target_name = os.path.split(targetdir)

                # Start httpd on the target
                runner.run('/bin/tar -cmzf /tmp/fs.tgz -C %s %s' % (parent_dir, target_name))
                runner.run('cd /tmp')  # need to be in same dir as fs.tgz

                url_base = self.start_http_server(runner)
                
                url = url_base + '/fs.tgz'
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
                    runner.run('rm -rf %s' % targetdir)
                    self._target_extract(runner, tf, parent_dir)

            finally:
                    self.stop_http_server(runner)
                    runner.run('umount /mnt')

    def start_http_server(self, runner, port=80):
        # busybox produces no output to parse for, so let it run as a daemon
        runner.run('busybox httpd -v -p %s' % port)
        url_base = "http://%s:%s" % (self.master_ip, port)
        return url_base

    def stop_http_server(self, runner):
        runner.run('killall busybox')

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
	    

    @contextlib.contextmanager
    def _as_master(self):
        self.bootcontrol.power_on_boot_master()

        # Two reboots seem to be necessary to ensure that pxe boot is used.
        # Need to identify the cause and fix it
        self.proc.expect("Hit any key to stop autoboot:")
        self.proc.sendline('')
        self.bootcontrol.power_reset_boot_master()

        self.proc.expect("\(initramfs\)")
        self.proc.sendline('export PS1="%s"' % self.MASTER_PS1)
        self.proc.expect(self.MASTER_PS1_PATTERN, timeout=180, lava_no_logging=1)
        runner = HBMasterCommandRunner(self)
        runner.run(". /scripts/functions")
        ip_pat = '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        device = "eth0"
        runner.run("DEVICE=%s configure_networking" % device,
                   response='dns0     : (%s) ' % ip_pat, wait_prompt=False)
        if runner.match_id != 0:
            msg = "Unable to determine dns address"
            logging.error(msg) 
            raise CriticalError(msg)
        dns = runner.match.group(1)
        logging.info("DNS Address is %s" % dns)
        runner.run("echo nameserver %s > /etc/resolv.conf" % dns)

        self.device_version = runner.get_device_version()

        try:
            self.master_ip = runner.get_master_ip()
            yield runner
        finally:
           logging.debug("deploy done")

	    
target_class = HighbankTarget


class HBMasterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the master image.
    """
    def __init__(self, target):
        super(HBMasterCommandRunner, self).__init__(
            target, target.MASTER_PS1_PATTERN, prompt_str_includes_rc=False)

    def get_master_ip(self):
        logging.info("Waiting for network to come up")
        try:
            self.wait_network_up(timeout=20)
        except NetworkError:
            logging.exception("Unable to reach LAVA server")
            raise

        ip_pat = '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        cmd = ("ifconfig %s | grep 'inet addr' | awk -F: '{print $2}' |"
                "awk '{print \"<\" $1 \">\"}'" %
                self._client.config.default_network_interface)
        self.run(cmd, response='(%s)' % ip_pat, wait_prompt=False)
        if self.match_id != 0:
            msg = "Unable to determine master image IP address"
            logging.error(msg)
            raise CriticalError(msg)
        ip = self.match.group(1)
        logging.debug("Master image IP is %s" % ip)
        return ip

    def get_device_version(self):
        # To be re-implemented when master image is generated by linaro-image-tools
        device_version = "unknown"
        return device_version

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

class IpmiPxeBoot(object):
    """
    This class provides a convenient object-oriented API that can be
    used to initiate power on/off and boot device selection for pxe
    and disk boot devices using ipmi commands.
    """

    def __init__(self, host):
        self.ipmitool = IPMITool(host)

    def power_on_boot_master(self):
        self.ipmitool.set_to_boot_from_pxe()
        self.ipmitool.power_on()
        self.ipmitool.reset()

    def power_reset_boot_master(self):
        self.ipmitool.set_to_boot_from_pxe()
        self.ipmitool.reset()

    def power_on_boot_image(self):
        self.ipmitool.set_to_boot_from_disk()
        self.ipmitool.power_on()
        self.ipmitool.reset()

    def power_off(self):
        self.ipmitool.power_off()


