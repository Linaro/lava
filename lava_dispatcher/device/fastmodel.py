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

import codecs
import contextlib
import cStringIO
import logging
import os
import subprocess
import signal
import pexpect

import lava_dispatcher.device.boot_options as boot_options

from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.client.base import (
    NetworkCommandRunner,
)
from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted,
    generate_android_image,
    generate_fastmodel_image,
)
from lava_dispatcher.downloader import (
    download_image,
)
from lava_dispatcher.test_data import (
    create_attachment,
)
from lava_dispatcher.errors import (
    CriticalError,
    OperationFailed,
)
from lava_dispatcher.utils import (
    extract_tar,
    DrainConsoleOutput,
    finalize_process,
    extract_overlay,
    extract_ramdisk,
    create_ramdisk,
    ensure_directory,
    touch,
)
from lava_dispatcher import deployment_data


class FastModelTarget(Target):

    ANDROID_WALLPAPER = 'system/wallpaper_info.xml'
    SYS_PARTITION = 2
    DATA_PARTITION = 5

    def __init__(self, context, config):
        super(FastModelTarget, self).__init__(context, config)

        self._sim_proc = None
        self._axf = None
        self._kernel = None
        self._dtb = None
        self._initrd = None
        self._uefi = None
        self._uefi_vars = None
        self._bl0 = None
        self._bl1 = None
        self._bl2 = None
        self._bl31 = None
        self._default_boot_cmds = None
        self._ramdisk_boot = False
        self._booted = False
        self._reset_boot = False
        self._in_test_shell = False
        self._bootloadertype = 'u_boot'
        self._boot_tags = {}
        self._scratch_dir = self.scratch_dir
        self._interface_name = None

    def _customize_android(self):
        self.deployment_data = deployment_data.android

        with image_partition_mounted(self._sd_image, self.DATA_PARTITION) as d:
            wallpaper = '%s/%s' % (d, self.ANDROID_WALLPAPER)
            # delete the android active wallpaper as slows things down
            self.context.run_command('sudo rm -f %s' % wallpaper)

        with image_partition_mounted(self._sd_image, self.SYS_PARTITION) as d:
            with open('%s/etc/mkshrc' % d, 'a') as f:
                f.write('\n# LAVA CUSTOMIZATIONS\n')
                # make sure PS1 is what we expect it to be
                f.write('PS1="%s"\n' % self.tester_ps1)
                if not self.config.enable_network_after_boot_android:
                    # fast model usermode networking does not support ping
                    f.write('alias ping="echo LAVA-ping override 1 received"\n')

    def _copy_needed_files_from_partition(self, partno, subdir):
        with image_partition_mounted(self._sd_image, partno) as mntdir:
            subdir = os.path.join(mntdir, subdir)
            self._copy_needed_files_from_directory(subdir)

    def _copy_needed_files_from_directory(self, subdir):
        odir = os.path.dirname(self._sd_image)
        if self._bootloadertype == 'u_boot':
            # Extract the bootwrapper from the image
            if self.config.simulator_axf_files and self._axf is None:
                self._axf = \
                    self._copy_first_find_from_list(subdir, odir,
                                                    self.config.simulator_axf_files)
        elif self._bootloadertype == 'uefi':
            # Extract the uefi binary from the image
            if self.config.simulator_uefi_files and self._uefi is None:
                self._uefi = \
                    self._copy_first_find_from_list(subdir, odir,
                                                    self.config.simulator_uefi_files)
                if self.config.simulator_uefi_vars and self._uefi_vars is None:
                    # Create file for flashloader1
                    self._uefi_vars = os.path.join(odir, self.config.simulator_uefi_vars)
                    touch(self._uefi_vars)

        # These are common to both AXF and UEFI
        # Extract the kernel from the image
        if self.config.simulator_kernel_files and self._kernel is None:
            self._kernel = \
                self._copy_first_find_from_list(subdir, odir,
                                                self.config.simulator_kernel_files,
                                                self.config.simulator_kernel)
        # Extract the initrd from the image
        if self.config.simulator_initrd_files and self._initrd is None:
            self._initrd = \
                self._copy_first_find_from_list(subdir, odir,
                                                self.config.simulator_initrd_files,
                                                self.config.simulator_initrd)
        # Extract the dtb from the image
        if self.config.simulator_dtb_files and self._dtb is None:
            self._dtb = \
                self._copy_first_find_from_list(subdir, odir,
                                                self.config.simulator_dtb_files,
                                                self.config.simulator_dtb)

            # workaround for renamed device tree blobs
            # see https://bugs.launchpad.net/linaro-oe/+bug/1255527
            dest_dtb = os.path.join(odir, 'fdt.dtb')
            if self._dtb and not os.path.exists(dest_dtb):
                os.symlink(self._dtb, dest_dtb)

        # Extract the first secure flashloader binary from the image
        if self.config.simulator_bl1_files and self._bl1 is None:
            self._bl1 = \
                self._copy_first_find_from_list(subdir, odir,
                                                self.config.simulator_bl1_files,
                                                self.config.simulator_bl1)
        # Extract the second secure flashloader binary from the image
        if self.config.simulator_bl2_files and self._bl2 is None:
            self._bl2 = \
                self._copy_first_find_from_list(subdir, odir,
                                                self.config.simulator_bl2_files,
                                                self.config.simulator_bl2)
        # Extract the second secure flashloader binary from the image
        if self.config.simulator_bl31_files and self._bl31 is None:
            self._bl31 = \
                self._copy_first_find_from_list(subdir, odir,
                                                self.config.simulator_bl31_files,
                                                self.config.simulator_bl31)

    def _check_needed_files(self):
        if self._bootloadertype == 'u_boot':
            # AXF is needed when we are not using UEFI
            if self._axf is None and self.config.simulator_axf_files:
                raise RuntimeError('No AXF found, %r' %
                                   self.config.simulator_axf_files)
        elif self._bootloadertype == 'uefi':
            # UEFI binary is needed when specified
            if self._uefi is None and self.config.simulator_uefi_files:
                raise RuntimeError('No UEFI binary found, %r' %
                                   self.config.simulator_uefi_files)
            if self._uefi_vars is None:
                logging.warning('No uefi-vars.fd found')

        # These are common to both AXF and UEFI
        if self._sd_image is None:
            raise RuntimeError('No IMAGE found, %r' %
                               self.config.simulator_kernel_files)
        # Kernel is needed only for b.L models
        if self._kernel is None and self.config.simulator_kernel_files:
            raise RuntimeError('No KERNEL found, %r' %
                               self.config.simulator_kernel_files)
        # Initrd is needed only for b.L models
        if self._initrd is None and self.config.simulator_initrd_files:
            logging.warning('No INITRD found, %r',
                            self.config.simulator_initrd_files)
        # DTB is needed only for b.L models
        if self._dtb is None and self.config.simulator_dtb_files:
            logging.warning('No DTB found, %r',
                            self.config.simulator_dtb_files)
        # SECURE FLASHLOADERs are needed only for base and cortex models
        if self._bl1 is None and self.config.simulator_bl1_files:
            raise RuntimeError('No SECURE FLASHLOADER found, %r' %
                               self.config.simulator_bl1_files)
        if self._bl2 is None and self.config.simulator_bl2_files:
            logging.warning('No SECURE FLASHLOADER found, %r',
                            self.config.simulator_bl2_files)
        if self._bl31 is None and self.config.simulator_bl31_files:
            logging.warning('No SECURE FLASHLOADER found, %r',
                            self.config.simulator_bl31_files)

    def deploy_android(self, images, rootfstype, bootloadertype,
                       target_type):
        logging.info("Deploying Android on %s", self.config.hostname)

        self._bootloadertype = bootloadertype
        self._boot = None
        self._system = None
        self._data = None

        for image in images:
            if 'boot' in image['partition']:
                self._boot = download_image(image['url'], self.context, decompress=False)
            elif 'system' in image['partition']:
                self._system = download_image(image['url'], self.context, decompress=False)
            elif 'userdata' in image['partition']:
                self._data = download_image(image['url'], self.context, decompress=False)
            else:
                msg = 'Unsupported partition option: %s' % image['partition']
                logging.warning(msg)
                raise CriticalError(msg)

        if not all([self._boot, self._system, self._data]):
            msg = 'Must supply a boot, system, and userdata image for fastmodel image deployment'
            logging.warning(msg)
            raise CriticalError(msg)

        self._sd_image = '%s/android.img' % os.path.dirname(self._system)

        generate_android_image(
            self.context, 'vexpress', self._boot, self._data, self._system, self._sd_image
        )

        self._copy_needed_files_from_partition(self.config.boot_part, '')

        self._customize_android()

    def deploy_linaro(self, hwpack, rootfs, dtb, rootfstype, bootfstype, bootloadertype, qemu_pflash=None):
        hwpack = download_image(hwpack, self.context, decompress=False)
        rootfs = download_image(rootfs, self.context, decompress=False)
        odir = os.path.dirname(rootfs)

        self._bootloadertype = bootloadertype

        generate_fastmodel_image(self.context, hwpack, rootfs, dtb, odir,
                                 bootloadertype)
        self._sd_image = '%s/sd.img' % odir
        self.customize_image(self._sd_image)

        self._copy_needed_files_from_partition(self.config.boot_part, '')
        self._copy_needed_files_from_partition(self.config.root_part, 'boot')
        self._copy_needed_files_from_partition(self.config.root_part, 'lib')

    def deploy_linaro_prebuilt(self, image, dtb, rootfstype, bootfstype, bootloadertype, qemu_pflash=None):
        self._sd_image = download_image(image, self.context)
        self._bootloadertype = bootloadertype
        self.customize_image(self._sd_image)

        if dtb is not None:
            self.config.simulator_dtb_files = [dtb]

        self._copy_needed_files_from_partition(self.config.boot_part, '')
        self._copy_needed_files_from_partition(self.config.root_part, 'boot')
        self._copy_needed_files_from_partition(self.config.root_part, 'lib')

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs, image, bootloader, firmware, bl0, bl1,
                             bl2, bl31, rootfstype, bootloadertype, target_type, qemu_pflash=None):
        # Required
        if kernel is None:
            raise CriticalError("A kernel image is required")
        elif ramdisk is None:
            raise CriticalError("A ramdisk image is required")

        if rootfs is not None or nfsrootfs is not None or firmware is not None:
            logging.warning("This platform only supports ramdisk booting, ignoring other parameters")

        self._ramdisk_boot = True

        self._kernel = download_image(kernel, self.context, self._scratch_dir,
                                      decompress=False)
        self._boot_tags['{KERNEL}'] = os.path.relpath(self._kernel, self._scratch_dir)
        self._initrd = download_image(ramdisk, self.context, self._scratch_dir,
                                      decompress=False)
        if overlays is not None:
            ramdisk_dir = extract_ramdisk(self._initrd, self._scratch_dir,
                                          is_uboot=self._is_uboot_ramdisk(ramdisk))
            for overlay in overlays:
                overlay = download_image(overlay, self.context,
                                         self._scratch_dir,
                                         decompress=False)
                extract_overlay(overlay, ramdisk_dir)
            self._initrd = create_ramdisk(ramdisk_dir, self._scratch_dir)
        self._boot_tags['{RAMDISK}'] = os.path.relpath(self._initrd, self._scratch_dir)

        # Optional
        if dtb is not None:
            self._dtb = download_image(dtb, self.context, self._scratch_dir,
                                       decompress=False)
            self._boot_tags['{DTB}'] = os.path.relpath(self._dtb, self._scratch_dir)

        if bootloader is None:
            if self.config.simulator_uefi_default is None:
                raise CriticalError("UEFI image is required")
            else:
                self._uefi = download_image(self.config.simulator_uefi_default, self.context,
                                            self._scratch_dir, decompress=False)
        else:
            self._uefi = download_image(bootloader, self.context,
                                        self._scratch_dir, decompress=False)

        if bl1 is None:
            if self.config.simulator_bl1_default is None:
                raise CriticalError("BL1 firmware is required")
            else:
                self._bl1 = download_image(self.config.simulator_bl1_default, self.context,
                                           self._scratch_dir, decompress=False)
        else:
            self._bl1 = download_image(bl1, self.context,
                                       self._scratch_dir, decompress=False)

        if bl0 is not None:
            self._bl0 = download_image(bl0, self.context, self._scratch_dir,
                                       decompress=False)
        if bl2 is not None:
            self._bl2 = download_image(bl2, self.context, self._scratch_dir,
                                       decompress=False)
        if bl31 is not None:
            self._bl31 = download_image(bl31, self.context, self._scratch_dir,
                                        decompress=False)

        if self.config.simulator_uefi_vars and self._uefi_vars is None:
            # Create file for flashloader1
            self._uefi_vars = os.path.join(self._scratch_dir, self.config.simulator_uefi_vars)
            touch(self._uefi_vars)

        # Get deployment data
        self.deployment_data = deployment_data.get(target_type)

        if image is not None:
            self._sd_image = download_image(image, self.context, self._scratch_dir,
                                            decompress=True)
        else:
            # Booting is not supported without an _sd_image defined
            self._sd_image = self._kernel

        self._default_boot_cmds = 'boot_cmds_ramdisk'

    def is_booted(self):
        return self._booted

    def reset_boot(self, in_test_shell=True):
        self._reset_boot = True
        self._booted = False
        self._in_test_shell = in_test_shell

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        if self._ramdisk_boot:
            if self._reset_boot:
                self._reset_boot = False
                if self._in_test_shell:
                    self._in_test_shell = False
                    raise Exception("Operation timed out, resetting platform!")
            elif not self._booted:
                self.context.client.boot_linaro_image()
            pat = self.tester_ps1_pattern
            incrc = self.tester_ps1_includes_rc
            runner = NetworkCommandRunner(self, pat, incrc)
            with self._busybox_file_system(runner, directory) as path:
                yield path
        else:
            self._check_power_state()
            with image_partition_mounted(self._sd_image, partition) as mntdir:
                path = '%s/%s' % (mntdir, directory)
                ensure_directory(path)
                yield path

    def extract_tarball(self, tarball_url, partition, directory='/'):
        logging.info('extracting %s to target', tarball_url)

        self._check_power_state()
        with image_partition_mounted(self._sd_image, partition) as mntdir:
            tb = download_image(tarball_url, self.context, decompress=False)
            extract_tar(tb, '%s/%s' % (mntdir, directory))

    def _fix_perms(self):
        """ The directory created for the image download/creation gets created
        with tempfile.mkdtemp which grants permission only to the creator of
        the directory. Since these are temporary files, we can make them readable
        by any user on the system.
        """
        outdir = os.path.dirname(self._sd_image)
        os.chmod(outdir, 0o777)
        for root, dirs, files in os.walk(outdir):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o777)
            for f in files:
                os.chmod(os.path.join(root, f), 0o777)

    def _check_power_state(self):
        if self._sim_proc is not None:
            logging.warning('device already powered on, powering off first')
            self.power_off(None)

    def power_off(self, proc):
        if self._sim_proc:
            try:
                self._soft_reboot(self.proc)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except:
                logging.info('Graceful reboot of platform failed')
        if self._uefi_vars is not None and self._sim_proc:
            logging.info('Requesting graceful shutdown')
            self._sim_proc.kill(signal.SIGTERM)
            self._sim_proc.wait()
        finalize_process(self._sim_proc)
        super(FastModelTarget, self).power_off(proc)
        self._sim_proc = None

    def _create_rtsm_ostream(self, ofile):
        """the RTSM binary uses the windows code page(cp1252), but the
        dashboard and celery needs data with a utf-8 encoding"""
        return codecs.EncodedFile(ofile, 'cp1252', 'utf-8')

    def _drain_sim_proc(self):
        """pexpect will continue to get data for the simproc process. We need
        to keep this pipe drained so that it won't get full and then stop block
        the process from continuing to execute"""

        f = cStringIO.StringIO()
        self._sim_proc.logfile = self._create_rtsm_ostream(f)
        DrainConsoleOutput(proc=self._sim_proc).start()

    def power_on(self):
        if self._ramdisk_boot and self._booted:
            self.proc.sendline('export PS1="%s"'
                               % self.tester_ps1,
                               send_char=self.config.send_char)
            return self.proc
        self._check_power_state()
        if self.config.bridged_networking:
            self._interface_name = os.path.basename(self._scratch_dir)
            if not self._bridge_configured:
                self._config_network_bridge(self.config.bridge_interface, self._interface_name)

        self._check_needed_files()

        self._fix_perms()

        if self.config.simulator_options is not None:
            logging.info('Overriding default simulator options')
            options = ' '.join(self.config.simulator_options)
        else:
            # If the user hasn't set their own flags then we should use the defaults
            cli_pattern = self.config.simulator_command_flag + '%s=%s' + ' '
            options = boot_options.as_string(self, join_pattern=cli_pattern)

        if self.config.simulator_boot_wrapper and self._uefi is None:
            options = '%s %s' % (self.config.simulator_boot_wrapper, options)

        sim_cmd = '%s %s' % (self.config.simulator_command, options)
        sim_cmd = sim_cmd.format(
            AXF=self._axf, IMG=self._sd_image, KERNEL=self._kernel,
            DTB=self._dtb, INITRD=self._initrd, UEFI=self._uefi, BL0=self._bl0,
            BL1=self._bl1, UEFI_VARS=self._uefi_vars, INTERFACE=self._interface_name)

        # the simulator proc only has stdout/stderr about the simulator
        # we hook up into a telnet port which emulates a serial console
        logging.info('launching fastmodel with command %r', sim_cmd)
        # The base and cortex models must be invoked from the output directory
        # to ensure that the secure firmware can chainload one another.
        # bl1 -> bl2 -> bl3.
        odir = os.path.dirname(self._sd_image)
        self._sim_proc = self.context.spawn(sim_cmd, cwd=odir, timeout=1200)
        self._sim_proc.expect(self.config.fvp_terminal_port_pattern, timeout=300)
        self._serial_port = self._sim_proc.match.groups()[0]
        logging.info('serial console port on: %s', self._serial_port)

        match = self._sim_proc.expect(["ERROR: License check failed!",
                                       "Simulation is started"])
        if match == 0:
            raise RuntimeError("fast model license check failed")

        self._drain_sim_proc()

        logging.info('simulator is started connecting to serial port')
        self.proc = self.context.spawn(
            'telnet localhost %s' % self._serial_port,
            timeout=1200)
        self.proc.logfile_read = self._create_rtsm_ostream(
            self.proc.logfile_read)

        if self._uefi:
            self._enter_bootloader(self.proc)
            boot_cmds = self._load_boot_cmds(default=self._default_boot_cmds,
                                             boot_tags=self._boot_tags)
            self._customize_bootloader(self.proc, boot_cmds)

        self._monitor_boot(self.proc, self.tester_ps1, self.tester_ps1_pattern)
        self._auto_login(self.proc)

        if self._ramdisk_boot:
            self._booted = True

        return self.proc

    def get_test_data_attachments(self):
        """returns attachments to go in the "lava_results" test run"""
        # if the simulator never got started we won't even get to a logfile
        if getattr(self._sim_proc, 'logfile', None) is not None:
            if getattr(self._sim_proc.logfile, 'getvalue', None) is not None:
                content = self._sim_proc.logfile.getvalue()
                return [create_attachment('rtsm.log', content)]
        return []

    def get_device_version(self):
        cmd = self.config.simulator_version_command
        try:
            return subprocess.check_output(cmd, shell=True).strip()
        except subprocess.CalledProcessError:
            return "unknown"


target_class = FastModelTarget
