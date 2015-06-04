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


import logging
import time

from lava_dispatcher.utils import finalize_process
from lava_dispatcher.errors import CriticalError
from lava_dispatcher.downloader import download_image
from lava_dispatcher.utils import (
    mkdtemp,
    connect_to_serial,
    extract_rootfs,
    extract_ramdisk,
    extract_overlay,
    create_ramdisk
)

import pexpect


class BaseDriver(object):

    def __init__(self, device):
        self.device = device
        self.context = device.context
        self.config = device.config
        self._default_boot_cmds = 'boot_cmds_ramdisk'

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs,
                             image, bootloader, firmware, bl0, bl1, bl2, bl31, rootfstype,
                             bootloadertype, target_type, scratch_dir, qemu_pflash=None):
        """
        """
        raise NotImplementedError("deploy_linaro_kernel")

    def connect(self, boot_cmds):
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

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs,
                             image, bootloader, firmware, bl0, bl1, bl2, bl31, rootfstype,
                             bootloadertype, target_type, scratch_dir, qemu_pflash=None):
        kernel_url = kernel
        dtb_url = dtb
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
            if overlays is not None:
                ramdisk_dir = extract_ramdisk(ramdisk, scratch_dir,
                                              is_uboot=False)
                for overlay in overlays:
                    overlay = download_image(overlay, self.context,
                                             scratch_dir,
                                             decompress=False)
                    extract_overlay(overlay, ramdisk_dir)
                ramdisk = create_ramdisk(ramdisk_dir, scratch_dir)
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
            if overlays is not None and ramdisk is None:
                for overlay in overlays:
                    overlay = download_image(overlay, self.context,
                                             scratch_dir,
                                             decompress=False)
                extract_overlay(overlay, lava_nfsrootfs)

        # Add suffix for boot commands
        self._stmc_command = stmc_command + ' --'

        if self.context.test_data.metadata.get('is_slave', 'false') == 'true':
            logging.info("Booting in the master/slave mode, as *slave*")
            logging.info("Sending the kernel, dtb, nfsrootfs urls")
            self.context.transport.request_send('lava_ms_slave_data',
                                                {'kernel': kernel_url,
                                                 'dtb': dtb_url if dtb_url else '',
                                                 'nfs_rootfs': lava_nfsrootfs,
                                                 'nfs_server_ip': self.context.config.lava_server_ip,
                                                 'stmc_ip': self.config.jtag_stmc_ip})

        return self._boot_tags, self._default_boot_cmds

    def stmc_status_ok(self):
        """
            Return the True if the STMC status is working. False overwise
        """
        command = "%s --ip %s --status" % (self.config.jtag_stmcconfig, self.config.jtag_stmc_ip)
        stmc_status = self.context.spawn(command, timeout=10)
        try:
            stmc_status.expect("STMC booted successfully")
        except Exception:
            return False
        return True

    def stmc_serial_relay(self):
        """
            Return True if the serial relay is working. False overwise
        """
        command = "%s --ip %s --serial-relay" % (self.config.jtag_stmcconfig, self.config.jtag_stmc_ip)
        stmc_serial_relay = self.context.spawn(command, timeout=10)
        try:
            stmc_serial_relay.expect("Starting serial relay : ip: %s port: 5331" % (self.config.jtag_stmc_ip))
        except Exception:
            return False
        return True

    def connect(self, boot_cmds):
        if self.context.test_data.metadata.get('is_slave', 'false') == 'true':
            # When booting in master-slave, the protocol is:
            # 1/ self  : reboot the STMC2
            # 2/ master: wait for the STMC2 prompt
            # 3/ self  : reboot the board
            # 4/ master: setup the serial relay
            # 5/ self  : connect to the serial
            # 6/ master: boot the board

            # Reboot the STMC2 when the master is ready
            self.context.transport.request_wait('lava_ms_reboot_STMC2')
            logging.info("Hard resetting STMC2")
            if not self.config.jtag_hard_reset_command:
                raise CriticalError("'jtag_hard_reset_command' is required")
            self.context.run_command(self.config.jtag_hard_reset_command)
            self.context.transport.request_send('lava_ms_reboot_STMC2_done', None)

            self.context.transport.request_wait('lava_ms_reboot_board')
            logging.info("Hard resetting platform")
            if not self.config.hard_reset_command:
                raise CriticalError("'hard_reset_command' is required")
            self.context.run_command(self.config.hard_reset_command)
            self.context.transport.request_send('lava_ms_reboot_board_done', None)

            # Connect to the STMC serial relay
            self.context.transport.request_wait('lava_ms_ready')
            logging.info("Connecting to STMC serial relay")
            proc = connect_to_serial(self.context)

            # Ask the master to deliver the image
            self.context.transport.request_send('lava_ms_boot', None)

        else:
            boot_cmds.insert(0, self._stmc_command)
            jtag_command = ' '.join(boot_cmds)

            # jtag_stmcconfig is required
            if not self.config.jtag_stmcconfig:
                raise CriticalError("STMC config command should be present")

            # Check the STMC status command
            logging.info("Checking STMC status")
            if not self.stmc_status_ok():
                logging.info("Hard resetting STMC")
                # JTAG hard reset is required
                if not self.config.jtag_hard_reset_command:
                    raise CriticalError("STMC is not working and 'jtag_hard_reset_command' is not set")

                self.context.run_command(self.config.jtag_hard_reset_command)
                logging.info("Waiting for STMC to initialize")
                success = False
                for loop_index in range(1, 5):
                    logging.info("  checking STMC status (%d)", loop_index)
                    if self.stmc_status_ok():
                        success = True
                        break
                    time.sleep(5)

                if not success:
                    raise CriticalError("The STMC fails to reboot after hard reset")

            # Hard reset platform
            if self.config.hard_reset_command:
                logging.info("Hard resetting platform")
                self.context.run_command(self.config.hard_reset_command)
            else:
                raise CriticalError("Must have a hard_reset_command defined")

            # Setup the serial-relay
            if not self.stmc_serial_relay():
                raise CriticalError("Unable to setup the serial relay. The STMC is not working properly")

            # Connect to the STMC serial relay
            logging.info("Connecting to STMC serial relay")
            proc = connect_to_serial(self.context)

            # Deliver images with STMC
            logging.info("Delivering images with STMC")
            # Boot the board with a timeout on this command that MUST finish on
            # time (the command block when failing to boot)
            boot_proc = self.context.spawn(jtag_command, timeout=240)
            try:
                boot_proc.expect(pexpect.EOF)
            except pexpect.TIMEOUT:
                raise CriticalError("GDB is unable to boot the board")

            logging.info("GDB has finished, waiting for the board prompt")

        # Wait for the prompt
        proc.expect(self.config.image_boot_msg,
                    timeout=self.config.image_boot_msg_timeout)
        return proc
