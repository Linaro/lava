# Copyright (C) 2013 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
# Derived From: dummy_drivers.py
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


from contextlib import contextmanager
import logging
import time

from lava_dispatcher.utils import finalize_process
from lava_dispatcher.errors import CriticalError
from lava_dispatcher.downloader import download_image
from lava_dispatcher.utils import (
    mkdtemp,
    connect_to_serial,
    extract_rootfs
)


class BaseDriver(object):

    def __init__(self, device):
        self.device = device
        self.context = device.context
        self.config = device.config
        self._default_boot_cmds = 'boot_cmds_ramdisk'

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, rootfs, nfsrootfs,
                             bootloader, firmware, rootfstype, bootloadertype,
                             target_type, scratch_dir):
        """
        """
        raise NotImplementedError("deploy_linaro_kernel")

    def connect(self):
        """
        """
        raise NotImplementedError("connect")

    def finalize(self, proc):
        finalize_process(proc)


class stmc(BaseDriver):

    def __init__(self, device):
        super(stmc, self).__init__(device)
        self._stmc_command = None
        self._boot_tags = {}
        self._booted = False

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, rootfs, nfsrootfs,
                             bootloader, firmware, rootfstype, bootloadertype,
                             target_type, scratch_dir):
        # At a minimum we must have a kernel
        if kernel is None:
            raise CriticalError("No kernel image to boot")
        # Set the server IP (Dispatcher)
        self._boot_tags['{SERVER_IP}'] = self.context.config.lava_server_ip
        # Get the JTAG command fragments
        stmc_command = ' '.join([self.config.jtag_stmc_boot_script,
                                 self.config.jtag_stmc_boot_options])
        # We have been passed kernel image
        kernel = download_image(kernel, self.context,
                                scratch_dir, decompress=False)
        stmc_command = ' '.join([stmc_command,
                                 self.config.jtag_stmc_kernel_command.format(KERNEL=kernel)])
        if ramdisk is not None:
            # We have been passed a ramdisk
            ramdisk = download_image(ramdisk, self.context,
                                     scratch_dir,
                                     decompress=False)
            stmc_command = ' '.join([stmc_command,
                                    self.config.jtag_stmc_ramdisk_command.format(RAMDISK=ramdisk)])
        if dtb is not None:
            # We have been passed a device tree blob
            dtb = download_image(dtb, self.context,
                                 scratch_dir, decompress=False)
            stmc_command = ' '.join([stmc_command,
                                    self.config.jtag_stmc_dtb_command.format(DTB=dtb)])
        if nfsrootfs is not None:
            # Extract rootfs into nfsrootfs directory
            nfsrootfs = download_image(nfsrootfs, self.context,
                                       scratch_dir,
                                       decompress=False)
            scratch_dir = mkdtemp(self.context.config.lava_image_tmpdir)
            lava_nfsrootfs = mkdtemp(basedir=scratch_dir)
            extract_rootfs(nfsrootfs, lava_nfsrootfs)
            self._boot_tags['{NFSROOTFS}'] = lava_nfsrootfs
            self._default_boot_cmds = 'boot_cmds_nfs'

        # Add suffix for boot commands
        self._stmc_command = stmc_command + ' --'

        return self._boot_tags, self._default_boot_cmds

    def connect(self, boot_cmds):
        boot_cmds.insert(0, self._stmc_command)
        jtag_command = ' '.join(boot_cmds)

        # JTAG hard reset
        if self.config.jtag_hard_reset_command:
            logging.info("Hard resetting STMC")
            self.context.run_command(self.config.jtag_hard_reset_command)
            logging.info("Waiting for %d seconds for STMC to initialize" %
                         self.config.jtag_hard_reset_sleep)
            time.sleep(self.config.jtag_hard_reset_sleep)

        # Hard reset platform
        if self.config.hard_reset_command:
            logging.info("Hard resetting platform")
            self.context.run_command(self.config.hard_reset_command)
        else:
            raise CriticalError("Must have a hard_reset_command defined")
        logging.info("Waiting for 20 seconds for platform to initialize")
        time.sleep(20)

        # Connect to the STMC serial relay
        logging.info("Connecting to STMC serial relay")
        proc = connect_to_serial(self.context)

        # Deliver images with STMC
        logging.info("Delivering images with STMC")
        self.context.run_command(jtag_command, failok=False)

        proc.expect(self.config.image_boot_msg, timeout=300)
        return proc
