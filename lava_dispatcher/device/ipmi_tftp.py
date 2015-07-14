# Copyright (C) 2012 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
# Author: Nicholas Schutt <nick.schutt@linaro.org>
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
import time

from lava_dispatcher.device.master import (
    MasterCommandRunner,
)
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.errors import (
    CriticalError,
)
from lava_dispatcher.downloader import (
    download_image,
)
from lava_dispatcher.utils import (
    mk_targz,
    rmtree,
    finalize_process,
)
from lava_dispatcher.client.lmc_utils import (
    generate_image,
)
from lava_dispatcher.ipmi import IpmiPxeBoot


class IpmiPxeTarget(Target):

    MASTER_PS1 = 'root@master [rc=$(echo \$?)]# '
    MASTER_PS1_PATTERN = 'root@master \[rc=(\d+)\]# '

    def __init__(self, context, config):
        super(IpmiPxeTarget, self).__init__(context, config)
        self.proc = self.context.spawn(self.config.connection_command, timeout=1200)
        if self.config.ecmeip is None:
            msg = "The ecmeip address is not set for this target"
            logging.error(msg)
            raise CriticalError(msg)
        self.bootcontrol = IpmiPxeBoot(context, self.config.ecmeip, self.config.ipmi_power_sleep,
                                       self.config.ipmi_power_retries)

    def power_on(self):
        self.bootcontrol.power_on_boot_image()
        self._monitor_boot(self.proc, self.tester_ps1, self.tester_ps1_pattern)
        return self.proc

    def power_off(self, proc):
        self.bootcontrol.power_off()
        finalize_process(self.proc)

    def deploy_linaro(self, hwpack, rfs, dtb, rootfstype, bootfstype, bootloadertype, qemu_pflash=None):
        image_file = generate_image(self, hwpack, rfs, dtb, self.scratch_dir,
                                    bootloadertype, rootfstype,
                                    extra_boot_args='1', image_size='1G')
        self.customize_image(image_file)
        self._deploy_image(image_file, '/dev/%s'
                           % self.config.sata_block_device)

    def deploy_linaro_prebuilt(self, image, dtb, rootfstype, bootfstype, bootloadertype, qemu_pflash=None):
        image_file = download_image(image, self.context, self.scratch_dir)
        self.customize_image(image_file)
        self._deploy_image(image_file, '/dev/%s'
                           % self.config.sata_block_device)

    def _deploy_image(self, image_file, device):
        with self._as_master() as runner:

            # erase the first part of the disk to make sure the new deploy works
            runner.run("dd if=/dev/zero of=%s bs=4M count=4" % device, timeout=1800)

            # compress the image to reduce the transfer size
            if not image_file.endswith('.bz2') and not image_file.endswith('gz'):
                os.system('bzip2 -9v ' + image_file)
                image_file += '.bz2'

            tmpdir = self.context.config.lava_image_tmpdir
            url = self.context.config.lava_image_url
            image_file = image_file.replace(tmpdir, '')
            image_url = '/'.join(u.strip('/') for u in [url, image_file])

            build_dir = '/builddir'
            image_file_base = build_dir + '/' + '/'.join(image_file.split('/')[-1:])

            decompression_cmd = None
            if image_file_base.endswith('.gz'):
                decompression_cmd = 'gzip -dc'
            elif image_file_base.endswith('.bz2'):
                decompression_cmd = 'bzip2 -dc'

            runner.run('mkdir %s' % build_dir)
            runner.run('mount -t tmpfs -o size=100%% tmpfs %s' % build_dir)
            runner.run('wget -O %s %s' % (image_file_base, image_url), timeout=1800)

            if decompression_cmd is not None:
                cmd = '%s %s | dd bs=4M of=%s' % (decompression_cmd, image_file_base, device)
            else:
                cmd = 'dd bs=4M if=%s of=%s' % (image_file_base, device)

            runner.run(cmd, timeout=1800)
            runner.run('umount %s' % build_dir)

            self.resize_rootfs_partition(runner)

    def get_partition(self, runner, partition):
        device = self.config.sata_block_device
        if partition == self.config.boot_part:
            partno = str(self.config.boot_part)
            partition = '/dev/%s%s' % (device, partno)
        elif partition == self.config.root_part:
            partno = str(self.config.root_part)
            partition = '/dev/%s%s' % (device, partno)
        else:
            raise RuntimeError(
                'unknown master image partition(%d)' % partition)
        return partition

    def resize_rootfs_partition(self, runner):
        partno = self.config.root_part
        start = None

        runner.run('parted -s /dev/%s print' % self.config.sata_block_device,
                   response='\s+%s\s+([0-9.]+.B)\s+\S+\s+\S+\s+primary\s+(\S+)' % partno,
                   wait_prompt=False)
        if runner.match_id != 0:
            msg = "Unable to determine rootfs partition"
            logging.warning(msg)
        else:
            start = runner.match.group(1)
            parttype = runner.match.group(2)

            if parttype == 'ext2' or parttype == 'ext3' or parttype == 'ext4':
                runner.run('parted -s /dev/%s rm %s'
                           % (self.config.sata_block_device, partno))
                runner.run('parted -s /dev/%s mkpart primary %s 100%%'
                           % (self.config.sata_block_device, start))
                runner.run('resize2fs -f /dev/%s%s'
                           % (self.config.sata_block_device, partno))
            elif parttype == 'brtfs':
                logging.warning("resize of btrfs partition not supported")
            else:
                logging.warning("unknown partition type for resize: %s", parttype)

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        logging.info('attempting to access master filesystem %r:%s',
                     partition, directory)

        assert directory != '/', "cannot mount entire partition"

        with self._as_master() as runner:
            runner.run('mkdir -p /mnt')
            partition = self.get_partition(runner, partition)
            runner.run('mount %s /mnt' % partition)
            with self._busybox_file_system(runner, directory, mounted=True) as path:
                yield path

    @contextlib.contextmanager
    def _as_master(self):
        self.bootcontrol.power_on_boot_master()
        self._enter_bootloader(self.proc)
        boot_cmds = self._load_boot_cmds(default='boot_cmds_master')
        self._customize_bootloader(self.proc, boot_cmds)
        self._monitor_boot(self.proc, self.MASTER_PS1, self.MASTER_PS1_PATTERN)
        runner = MasterCommandRunner(self)
        logging.info("System is in master image now")

        try:
            yield runner
        finally:
            logging.debug("deploy done")


target_class = IpmiPxeTarget
