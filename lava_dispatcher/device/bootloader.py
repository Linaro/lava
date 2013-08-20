# Copyright (C) 2013 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
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

import logging
import contextlib
import time
import os
import pexpect

from lava_dispatcher.device.master import (
    MasterImageTarget
)
from lava_dispatcher.client.base import (
    NetworkCommandRunner,
)
from lava_dispatcher.utils import (
    string_to_list,
    mk_targz,
    rmtree,
)
from lava_dispatcher.errors import (
    CriticalError,
    OperationFailed,
)
from lava_dispatcher.downloader import (
    download_image,
    download_with_retry,
)

class BootloaderTarget(MasterImageTarget):

    def __init__(self, context, config):
        super(BootloaderTarget, self).__init__(context, config)
        self._booted = False
        self._boot_cmds = None
        self._lava_cmds = None
        self._uboot_boot = False
        self._http_pid = None
        # This is the offset into the path, used to reference bootfiles
        self._offset = self.scratch_dir.index('images')

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, rootfs, bootloader,
                             firmware, rootfstype, bootloadertype):
         if bootloadertype == "u_boot":
             # We assume we will be controlling u-boot
             if kernel is not None:
                 # We have been passed kernel image, setup TFTP boot
                 self._uboot_boot = True
                 # We are not booted yet
                 self._booted = False
                 # TODO Maybe this must be passed in?
                 self.deployment_data = self.target_map['oe']
                 # Set the TFTP server IP (Dispatcher)
                 self._lava_cmds = "lava_server_ip=" + self.context.config.lava_server_ip + ","
                 kernel = download_image(kernel, self.context, 
                                         self.scratch_dir, decompress=False)
                 self._lava_cmds += "lava_kernel=" + kernel[self._offset::] + ","
                 if ramdisk is not None:
                     # We have been passed a ramdisk
                     ramdisk = download_image(ramdisk, self.context, 
                                              self.scratch_dir, 
                                              decompress=False)
                     self._lava_cmds += "lava_ramdisk=" + ramdisk[self._offset::] + ","
                 if dtb is not None:
                     # We have been passed a device tree blob
                     dtb = download_image(dtb, self.context, 
                                          self.scratch_dir, decompress=False)
                     self._lava_cmds += "lava_dtb=" + dtb[self._offset::] + ","
                 if rootfs is not None:
                     # We have been passed a rootfs
                     rootfs = download_image(rootfs, self.context, 
                                             self.scratch_dir, decompress=False)
                     self._lava_cmds += "lava_rootfs=" + rootfs[self._offset::] + ","
                 if bootloader is not None:
                     # We have been passed a bootloader
                     bootloader = download_image(bootloader, self.context, 
                                                 self.scratch_dir, 
                                                 decompress=False)
                     self._lava_cmds += "lava_bootloader=" + bootloader[self._offset::] + ","
                 if firmware is not None:
                     # We have been passed firmware
                     firmware = download_image(firmware, self.context, 
                                               self.scratch_dir, 
                                               decompress=False)
                     self._lava_cmds += "lava_firmware=" + firmware[self._offset::] + ","
             else:
                 # This *should* never happen
                 raise CriticalError("No kernel images to boot")
         else:
             # Define other "types" of bootloaders here. UEFI? Grub?
             raise CriticalError("U-Boot is the only supported bootloader at this time")

    def deploy_linaro(self, hwpack, rfs, bootloader):
        self._uboot_boot = False
        super(BootloaderTarget, self).deploy_linaro(hwpack, rfs, bootloader)

    def deploy_linaro_prebuilt(self, image):
        self._uboot_boot = False
        super(BootloaderTarget, self).deploy_linaro_prebuilt(image)

    def _inject_boot_cmds(self):
        if isinstance(self.config.boot_cmds, basestring):
            if self.config.boot_cmds_tftp is None:
                raise CriticalError("No TFTP boot commands defined")
            else:
                self._boot_cmds = self._lava_cmds + self.config.boot_cmds_tftp
                self._boot_cmds = string_to_list(self._boot_cmds.encode('ascii'))
        else:
            self._boot_cmds = string_to_list(self._lava_cmds.encode('ascii')) + self.config.boot_cmds

    def _run_boot(self):
        self._enter_bootloader(self.proc)
        self._inject_boot_cmds()
        self._customize_bootloader(self.proc, self._boot_cmds)
        self._wait_for_prompt(self.proc, ['\(initramfs\)', 
                              self.config.master_str],
                              self.config.boot_linaro_timeout)

    def _boot_linaro_image(self):            
        if self._uboot_boot and not self._booted:
            try:
                if self.config.hard_reset_command:
                    self._hard_reboot()
                    self._run_boot()
                else:
                   self._soft_reboot()
                   self._run_boot()
            except:
                logging.exception("_run_boot failed")
            self.proc.sendline('export PS1="%s"' 
                               % self.deployment_data['TESTER_PS1'])
            self._booted = True
        elif self._uboot_boot and self._booted:
            self.proc.sendline('export PS1="%s"' 
                               % self.deployment_data['TESTER_PS1'])
        else:
            super(BootloaderTarget, self)._boot_linaro_image()

    def start_http_server(self, runner, ip):
        if self._http_pid is not None:
            raise OperationFailed("busybox httpd already running with pid %d" % self._http_pid)
        # busybox produces no output to parse for, so run it in the bg and get its pid
        runner.run('busybox httpd -f &')
        runner.run('echo pid:$!:pid', response="pid:(\d+):pid", timeout=10)
        if runner.match_id != 0:
            raise OperationFailed("busybox httpd did not start")
        else:
            self._http_pid = runner.match.group(1)
        url_base = "http://%s" % ip
        return url_base

    def stop_http_server(self, runner):
        if self._http_pid is None:
            raise OperationFailed("busybox httpd not running, but stop_http_server called.")
        runner.run('kill %s' % self._http_pid)
        self._http_pid = None

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        if self._uboot_boot:
            try:
                pat = self.deployment_data['TESTER_PS1_PATTERN']
                incrc = self.deployment_data['TESTER_PS1_INCLUDES_RC']
                runner = NetworkCommandRunner(self, pat, incrc)

                targetdir = '/%s' % directory
                runner.run('mkdir -p %s' % targetdir)
                parent_dir, target_name = os.path.split(targetdir)
                runner.run('/bin/tar -cmzf /tmp/fs.tgz -C %s %s' % (parent_dir, target_name))
                runner.run('cd /tmp')  # need to be in same dir as fs.tgz

                ip = runner.get_target_ip()
                url_base = self.start_http_server(runner, ip)

                url = url_base + '/fs.tgz'
                logging.info("Fetching url: %s" % url)
                tf = download_with_retry(self.context, self.scratch_dir, url, False)

                tfdir = os.path.join(self.scratch_dir, str(time.time()))

                try:
                    os.mkdir(tfdir)
                    self.context.run_command('/bin/tar -C %s -xzf %s' % (tfdir, tf))
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
        else:
            super(BootloaderTarget, self).file_system(partition, directory)

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

target_class = BootloaderTarget
