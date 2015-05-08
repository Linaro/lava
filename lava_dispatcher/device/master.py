# Copyright (C) 2011 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
# Author: Paul Larson <paul.larson@linaro.org>
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

import contextlib
import logging
import os
import time
import re
import hashlib
import pexpect
import subprocess
from lava_dispatcher import tarballcache

from lava_dispatcher.client.base import (
    NetworkCommandRunner,
)
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.downloader import (
    download_image,
)
from lava_dispatcher.errors import (
    NetworkError,
    CriticalError,
    OperationFailed,
)
from lava_dispatcher.utils import (
    connect_to_serial,
    mk_targz,
    rmtree,
    mkdtemp,
    extract_tar,
    finalize_process,
)
from lava_dispatcher.client.lmc_utils import (
    generate_image,
    image_partition_mounted,
)
from lava_dispatcher import deployment_data


class MasterImageTarget(Target):

    MASTER_PS1 = ' [rc=$(echo \$?)]# '
    MASTER_PS1_PATTERN = ' \[rc=(\d+)\]# '

    def __init__(self, context, config):
        super(MasterImageTarget, self).__init__(context, config)

        # Update variable according to config file
        self.MASTER_PS1 = self.config.master_str + self.MASTER_PS1
        self.MASTER_PS1_PATTERN = self.config.master_str + self.MASTER_PS1_PATTERN

        self.master_ip = None
        self.device_version = None

        self.testboot_dir = self.config.master_testboot_dir
        self.testboot_label = self.config.master_testboot_label
        self.testboot_path = '%s%s' % (self.testboot_dir, self.testboot_label)

        self.testrootfs_dir = self.config.master_testrootfs_dir
        self.testrootfs_label = self.config.master_testrootfs_label
        self.testrootfs_path = '%s%s' % (self.testrootfs_dir, self.testrootfs_label)

        self.sdcard_dir = self.config.master_sdcard_dir
        self.sdcard_label = self.config.master_sdcard_label
        self.sdcard_path = '%s%s' % (self.sdcard_dir, self.sdcard_label)

        self.userdata_dir = self.config.master_userdata_dir
        self.userdata_label = self.config.master_userdata_label
        self.userdata_path = '%s%s' % (self.userdata_dir, self.userdata_label)

        self.master_kernel = None
        self.master_ramdisk = None
        self.master_overlays = None
        self.master_dtb = None
        self.master_firmware = None
        self.master_nfsrootfs = None
        self.master_base_tmpdir, self.master_tmpdir = self._setup_tmpdir()
        self.master_boot_tags = {}

        if config.pre_connect_command:
            self.context.run_command(config.pre_connect_command)

        self.proc = None

        self.__boot_cmds_dynamic__ = None

    def get_device_version(self):
        return self.device_version

    def power_on(self):
        self._boot_linaro_image()
        return self.proc

    def power_off(self, proc):
        if self.config.power_off_cmd != "":
            self.context.run_command(self.config.power_off_cmd)
        else:
            proc.send("~$")
            proc.sendline("off")
        finalize_process(self.proc)
        self.proc = None

    def deploy_linaro(self, hwpack, rfs, dtb, rootfstype, bootloadertype, qemu_pflash=None):
        self.boot_master_image()

        image_file = generate_image(self, hwpack, rfs, dtb, self.scratch_dir,
                                    bootloadertype, rootfstype)
        (boot_tgz, root_tgz, distro) = self._generate_tarballs(image_file)

        self._read_boot_cmds(boot_tgz=boot_tgz)
        self._deploy_tarballs(boot_tgz, root_tgz, rootfstype)

    def deploy_android(self, images, rootfstype,
                       bootloadertype, target_type):
        self.deployment_data = deployment_data.android
        self.boot_master_image()
        boot = None
        system = None
        data = None

        sdir = self.scratch_dir

        for image in images:
            if 'boot' in image['partition']:
                boot = download_image(image['url'], self.context, sdir, decompress=False)
            elif 'system' in image['partition']:
                system = download_image(image['url'], self.context, sdir, decompress=False)
            elif 'userdata' in image['partition']:
                data = download_image(image['url'], self.context, sdir, decompress=False)
            else:
                msg = 'Unsupported partition option: %s' % image['partition']
                logging.warning(msg)
                raise CriticalError(msg)

        if not all([boot, system, data]):
            msg = 'Must supply a boot, system, and userdata image for master image deployment'
            logging.warning(msg)
            raise CriticalError(msg)

        with self._as_master() as master:
            self._format_testpartition(master, rootfstype)
            self._deploy_android_tarballs(master, boot, system, data)

            if master.has_partition_with_label(self.userdata_label) and \
                    master.has_partition_with_label(self.sdcard_label):
                self._purge_linaro_android_sdcard(master)

    def _deploy_android_tarballs(self, master, boot, system, data):
        tmpdir = self.context.config.lava_image_tmpdir
        url = self.context.config.lava_image_url

        boot = boot.replace(tmpdir, '')
        system = system.replace(tmpdir, '')
        data = data.replace(tmpdir, '')

        boot_url = '/'.join(u.strip('/') for u in [url, boot])
        system_url = '/'.join(u.strip('/') for u in [url, system])
        data_url = '/'.join(u.strip('/') for u in [url, data])

        self._deploy_linaro_android_boot(master, boot_url, self)
        self._deploy_linaro_android_system(master, system_url)
        self._deploy_linaro_android_data(master, data_url)

    def deploy_linaro_prebuilt(self, image, dtb, rootfstype, bootloadertype, qemu_pflash=None):
        self.boot_master_image()

        if self.context.job_data.get('health_check', False):
            (boot_tgz, root_tgz, distro) = tarballcache.get_tarballs(
                self.context, image, self.scratch_dir, self._generate_tarballs)
            self.deployment_data = deployment_data.get(distro)
        else:
            image_file = download_image(image, self.context, self.scratch_dir)
            (boot_tgz, root_tgz, distro) = self._generate_tarballs(image_file)

        self._read_boot_cmds(boot_tgz=boot_tgz)
        self._deploy_tarballs(boot_tgz, root_tgz, rootfstype)

    def _deploy_tarballs(self, boot_tgz, root_tgz, rootfstype):
        tmpdir = self.context.config.lava_image_tmpdir
        url = self.context.config.lava_image_url

        boot_tarball = boot_tgz.replace(tmpdir, '')
        root_tarball = root_tgz.replace(tmpdir, '')
        boot_url = '/'.join(u.strip('/') for u in [url, boot_tarball])
        root_url = '/'.join(u.strip('/') for u in [url, root_tarball])
        with self._as_master() as master:
            self._format_testpartition(master, rootfstype)
            try:
                self._deploy_linaro_rootfs(master, root_url, rootfstype)
                self._deploy_linaro_bootfs(master, boot_url)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except:
                logging.exception("Deployment failed")
                raise CriticalError("Deployment failed")

    def _rewrite_uboot_partition_number(self, matchobj):
        """ Returns the uboot partition number after rewriting it to
        n + testboot_offset.
        """
        boot_device = str(self.config.boot_device)
        testboot_offset = self.config.testboot_offset
        partition = int(matchobj.group('partition')) + testboot_offset
        if self.config.testboot_partition is not None:
            return ' ' + boot_device + ':' + self.config.testboot_partition + ' '
        else:
            return ' ' + boot_device + ':' + str(partition) + ' '

    def _rewrite_rootfs_partition_number(self, matchobj):
        """ Returns the rootfs partition number after rewriting it to
        n + testboot_offset.
        """
        testboot_offset = self.config.testboot_offset
        prefix_len = len(matchobj.group(0)) - len(matchobj.group(1))
        return matchobj.group(0)[:prefix_len] + str(int(matchobj.group(1)) + testboot_offset)

    def _rewrite_boot_cmds(self, boot_cmds):
        """
        Returns boot_cmds list after rewriting things such as:

        * partition number from n to n + testboot_offset
        * root=LABEL=testrootfs instead of root=UUID=ab34-...
        * root=/dev/mmcblk0p5 instead of root=/dev/mmcblk0p3...
        """

        boot_cmds = re.sub(
            r"root=UUID=\S+", "root=LABEL=%s" % self.testrootfs_label, boot_cmds, re.MULTILINE)

        pattern = 'root=/\S+(?:\D|^)(\d+)'
        boot_cmds = re.sub(pattern, self._rewrite_rootfs_partition_number,
                           boot_cmds, re.MULTILINE)

        pattern = "\s+\d+:(?P<partition>\d+)\s+"
        boot_cmds = re.sub(
            pattern, self._rewrite_uboot_partition_number, boot_cmds, re.MULTILINE)

        return boot_cmds.split('\n')

    def _read_boot_cmds(self, image=None, boot_tgz=None):
        boot_file_path = None

        if not self.config.read_boot_cmds_from_image:
            return

        # If we have already obtained boot commands dynamically, then return.
        if self.__boot_cmds_dynamic__ is not None:
            logging.debug("We already have boot commands in place.")
            return

        if image:
            boot_part = self.config.boot_part
            # Read boot related file from the boot partition of image.
            with image_partition_mounted(image, boot_part) as mnt:
                for boot_file in self.config.boot_files:
                    boot_path = os.path.join(mnt, boot_file)
                    if os.path.exists(boot_path):
                        boot_file_path = boot_path
                        break

        elif boot_tgz:
            tmp_dir = mkdtemp()
            extracted_files = extract_tar(boot_tgz, tmp_dir)
            for boot_file in self.config.boot_files:
                for file_path in extracted_files:
                    if boot_file == os.path.basename(file_path):
                        boot_file_path = file_path
                        break

        if boot_file_path and os.path.exists(boot_file_path):
            with open(boot_file_path, 'r') as f:
                boot_cmds = self._rewrite_boot_cmds(f.read())
                self.__boot_cmds_dynamic__ = boot_cmds
        else:
            logging.debug("Unable to read boot commands dynamically.")

    def _format_testpartition(self, runner, fstype):
        try:
            force = ""
            logging.info("Format testboot and testrootfs partitions")
            if fstype.startswith("ext"):
                force = "-F"
            elif fstype == "btrfs":
                force = "-f"

            runner.run('umount %s' % self.testrootfs_path, failok=True)
            runner.run('nice mkfs %s -t %s -q %s -L %s'
                       % (force, fstype, self.testrootfs_path, self.testrootfs_label), timeout=1800)
            runner.run('umount %s' % self.testboot_path, failok=True)
            runner.run('nice mkfs.vfat %s -n %s' % (self.testboot_path, self.testboot_label))
            self.context.test_data.add_result('format_test_partition_in_master_image',
                                              'pass')
        except:
            msg = 'Master Image Error: could not format test partition'
            logging.error(msg)
            self.context.test_data.add_result('format_test_partition_in_master_image',
                                              'fail')
            raise

    def _generate_tarballs(self, image_file):
        self.customize_image(image_file)
        self._read_boot_cmds(image=image_file)
        boot_tgz = os.path.join(self.scratch_dir, "boot.tgz")
        root_tgz = os.path.join(self.scratch_dir, "root.tgz")
        try:
            _extract_partition(image_file, self.config.boot_part, boot_tgz)
            _extract_partition(image_file, self.config.root_part, root_tgz)
            self.context.test_data.add_result('generate_tar_balls_in_master_image',
                                              'pass')
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            msg = 'Master Image Error: failed to generate tarballs'
            logging.error(msg)
            self.context.test_data.add_result('generate_tar_balls_in_master_image',
                                              'fail')
            raise

        return boot_tgz, root_tgz, self.deployment_data['distro']

    def target_extract(self, runner, tar_url, dest, timeout=-1, num_retry=5):
        decompression_char = ''
        if tar_url.endswith('.gz') or tar_url.endswith('.tgz'):
            decompression_char = 'z'
        elif tar_url.endswith('.bz2'):
            decompression_char = 'j'
        else:
            msg = 'Master Image Error: bad file extension: %s' % tar_url
            self.context.test_data.add_result('extract_tar_ball_in_master_image',
                                              'fail')
            raise RuntimeError(msg)

        # we know that tar is new enough on the dispatcher via the packaging but
        # also need to look for support for a new enough version of tar in the master
        # image, without breaking jobs on older master images.
        if self._image_has_selinux_support(runner, 3):
            self.context.selinux = '--selinux'
        else:
            self.context.selinux = ''

        # handle root.tgz
        while num_retry > 0:
            try:
                runner.run(
                    'wget --no-check-certificate --no-proxy '
                    '--connect-timeout=30 -S --progress=dot -e dotbytes=2M '
                    '-O- %s | '
                    'tar %s --warning=no-timestamp --numeric-owner -C %s -x%sf -'
                    % (tar_url, self.context.selinux, dest, decompression_char),
                    timeout=timeout)
                self.context.test_data.add_result('extract_tar_ball_in_master_image',
                                                  'pass')
                return
            except (OperationFailed, pexpect.TIMEOUT):
                logging.warning("transfering %s failed. %d retry left.",
                                tar_url, num_retry - 1)

            if num_retry > 1:
                # send CTRL C in case wget still hasn't exited.
                self.proc.sendcontrol("c")
                self._wait_for_prompt(self.proc,
                                      self.MASTER_PS1_PATTERN,
                                      timeout=30)
                self.proc.sendline(
                    "echo 'retry left %s time(s)'" % (num_retry - 1))
                # And wait a little while.
                sleep_time = 60
                logging.info("Wait %d second before retry", sleep_time)
                time.sleep(sleep_time)
            num_retry -= 1
        msg = 'Master Image Error: extracting %s on target failed' % tar_url
        self.context.test_data.add_result('extract_tar_ball_in_master_image',
                                          'fail')
        raise RuntimeError(msg)

    def get_partition(self, runner, partition):
        if partition == self.config.boot_part:
            partition = self.testboot_path
        elif partition == self.config.root_part:
            partition = self.testrootfs_path
        elif partition == self.config.sdcard_part_android_org:
            partition = self.sdcard_path
        elif partition == self.config.data_part_android_org:
            lbl, partition = self._android_data_label(runner)
        else:
            raise RuntimeError(
                'unknown master image partition(%d)' % partition)
        return partition

    def extract_tarball(self, tarball_url, partition, directory='/'):
        logging.info('extracting %s to target', tarball_url)

        with self._as_master() as runner:
            partition = self.get_partition(runner, partition)
            runner.run('mount %s /mnt' % partition)
            try:
                self.target_extract(runner, tarball_url, '/mnt/%s' % directory)
            finally:
                runner.run('umount /mnt', timeout=3600)

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        logging.info('attempting to access master filesystem %r:%s',
                     partition, directory)

        assert directory != '/', "cannot mount entire partition"

        with self._as_master() as runner:
            partition = self.get_partition(runner, partition)
            runner.run('mount %s /mnt' % partition)
            with self._python_file_system(runner, directory, self.MASTER_PS1_PATTERN, mounted=True) as root:
                yield root

    def _wait_for_master_boot(self):
        if self.config.boot_cmds_master:
            # Break the boot sequence
            self._enter_bootloader(self.proc)
            # Configure dynamic master image boot
            if self.config.master_kernel and self.master_kernel is None:
                # Set the server IP (Dispatcher)
                self.master_boot_tags['{SERVER_IP}'] = self.context.config.lava_server_ip
                self.master_kernel = download_image(
                    self.config.master_kernel, self.context,
                    self.master_tmpdir, decompress=False)
                self.master_boot_tags['{KERNEL}'] = self._get_rel_path(self.master_kernel, self.master_base_tmpdir)
                if self.config.master_ramdisk:
                    self.master_ramdisk = download_image(
                        self.config.master_ramdisk, self.context,
                        self.master_tmpdir, decompress=False)
                    self.master_boot_tags['{RAMDISK}'] = self._get_rel_path(self.master_ramdisk, self.master_base_tmpdir)
                if self.config.master_dtb:
                    self.master_dtb = download_image(
                        self.config.master_dtb, self.context,
                        self.master_tmpdir, decompress=False)
                    self.master_boot_tags['{DTB}'] = self._get_rel_path(self.master_dtb, self.master_base_tmpdir)
                if self.config.master_firmware:
                    self.master_firmware = download_image(
                        self.config.master_firmware, self.context,
                        self.master_tmpdir, decompress=False)
                    self.master_boot_tags['{FIRMWARE}'] = self._get_rel_path(self.master_firmware, self.master_base_tmpdir)
                if self.config.master_nfsrootfs:
                    self.master_nfsrootfs = download_image(
                        self.config.master_nfsrootfs, self.context,
                        self.master_tmpdir, decompress=False)
                    self.master_boot_tags['{NFSROOTFS}'] = self._setup_nfs(self.master_nfsrootfs, self.master_tmpdir)
            boot_cmds = self._load_boot_cmds(default='boot_cmds_master',
                                             boot_tags=self.master_boot_tags)
            self._customize_bootloader(self.proc, boot_cmds)
        self._monitor_boot(self.proc, self.MASTER_PS1, self.MASTER_PS1_PATTERN, is_master=True)

    def boot_master_image(self):
        """
        reboot the system, and check that we are in a master shell
        """
        self.context.client.vm_group.wait_for_vms()

        boot_attempts = self.config.boot_retries
        attempts = 0
        in_master_image = False
        while (attempts < boot_attempts) and (not in_master_image):
            logging.info("Booting the system master image. Attempt: %d",
                         attempts + 1)
            try:
                if self.proc:
                    finalize_process(self.proc)
                    self.proc = None
                self.proc = connect_to_serial(self.context)
                self.master_ip = None
                if self.config.hard_reset_command:
                    self._hard_reboot(self.proc)
                    self._load_master_firmware()
                    self._wait_for_master_boot()
                else:
                    self._soft_reboot(self.proc)
                    self._load_master_firmware()
                    self._wait_for_master_boot()
            except (OperationFailed, pexpect.TIMEOUT) as e:
                msg = "Resetting platform into master image failed: %s" % e
                logging.warning(msg)
                attempts += 1
                continue

            runner = MasterCommandRunner(self)
            try:
                self.master_ip = runner.get_target_ip()
                self.device_version = runner.get_device_version()
            except NetworkError as e:
                msg = "Failed to get network up: %s" % e
                logging.warning(msg)
                attempts += 1
                continue

            lava_proxy = self.context.config.lava_proxy
            if lava_proxy:
                logging.info("Setting up http proxy")
                runner.run("export http_proxy=%s" % lava_proxy, timeout=30)
            lava_no_proxy = self.context.config.lava_no_proxy
            if lava_no_proxy:
                runner.run("export no_proxy=%s" % lava_no_proxy, timeout=30)
            logging.info("System is in master image now")
            self.context.test_data.add_result('boot_master_image',
                                              'pass')
            in_master_image = True

        if not in_master_image:
            msg = "Master Image Error: Could not get master image booted properly"
            logging.error(msg)
            self.context.test_data.add_result('boot_master_image',
                                              'fail')
            raise CriticalError(msg)

    @contextlib.contextmanager
    def _as_master(self):
        """A session that can be used to run commands in the master image."""
        if self.proc is not None:
            self.proc.sendline("")
            match_id = self.proc.expect(
                [self.MASTER_PS1_PATTERN, pexpect.TIMEOUT],
                timeout=10, lava_no_logging=1)
            if match_id == 1:
                self.boot_master_image()
        else:
            self.boot_master_image()

        yield MasterCommandRunner(self)

    def _boot_linaro_image(self):

        if self.__boot_cmds_dynamic__ is not None:
            boot_cmds = self._load_boot_cmds(boot_cmds_dynamic=self.__boot_cmds_dynamic__)
        else:
            boot_cmds = self._load_boot_cmds()

        logging.info('boot_cmds: %s', boot_cmds)

        self._boot(boot_cmds)

    def _load_test_firmware(self):
        # Do nothing by default
        pass

    def _load_master_firmware(self):
        # Do nothing by default
        pass

    def _boot(self, boot_cmds):
        self.master_ip = None
        if self.config.hard_reset_command:
            self._hard_reboot(self.proc)
            self._load_test_firmware()
            self._enter_bootloader(self.proc)
        else:
            self._soft_reboot(self.proc)
            self._load_test_firmware()
            self._enter_bootloader(self.proc)
        self._customize_bootloader(self.proc, boot_cmds)
        self._monitor_boot(self.proc, self.tester_ps1, self.tester_ps1_pattern)

    def _android_data_label(self, session):
        data_label = self.userdata_label
        data_path = self.userdata_path
        if not session.has_partition_with_label(data_label):
            # consider the compatiblity, here use the existed sdcard partition
            data_label = self.sdcard_label
            data_path = self.sdcard_path
        return data_label, data_path

    def _deploy_linaro_android_data(self, session, datatbz2):
        try:
            logging.info("Deploying Android data fs")
            data_label, data_path = self._android_data_label(session)
            session.run('umount %s' % data_path, failok=True)
            session.run('nice mkfs.ext4 -F -q %s -L %s' %
                        (data_path, data_label))
            session.run('udevadm trigger')
            session.run('mkdir -p /mnt/lava/data')
            session.run('mount %s /mnt/lava/data' % data_path)
            _test_filesystem_writeable(session, '/mnt/lava/data')
            session._client.target_extract(session, datatbz2, '/mnt/lava', timeout=600)
            session.run('umount /mnt/lava/data', timeout=3600)
            self.context.test_data.add_result('deploy_android_datafs_in_master_image',
                                              'pass')
        except:
            msg = 'Master Image Error: unable to deploy android data filesystem'
            logging.error(msg)
            self.context.test_data.add_result('deploy_android_datafs_in_master_image',
                                              'fail')
            raise

    def _deploy_linaro_bootfs(self, session, bootfs):
        try:
            logging.info("Deploying linaro boot fs")
            session.run('udevadm trigger')
            session.run('mkdir -p /mnt/boot')
            session.run('mount %s /mnt/boot' % self.testboot_path)
            _test_filesystem_writeable(session, '/mnt/boot')
            session._client.target_extract(session, bootfs, '/mnt/boot')
            session.run('umount /mnt/boot', timeout=3600)
            self.context.test_data.add_result('deploy_bootfs_in_master_image',
                                              'pass')
        except:
            msg = 'Master Image Error: unable to deploy test boot filesystem'
            logging.error(msg)
            self.context.test_data.add_result('deploy_bootfs_in_master_image',
                                              'fail')
            raise

    def _deploy_linaro_android_boot(self, session, boottbz2, target):
        try:
            logging.info("Deploying Android boot fs")
            session.run('mkdir -p /mnt/lava/boot')
            session.run('mount %s /mnt/lava/boot' % self.testboot_path)
            _test_filesystem_writeable(session, '/mnt/lava/boot')
            session._client.target_extract(session, boottbz2, '/mnt/lava')
            _recreate_ramdisk(session, target)
            session.run('umount /mnt/lava/boot', timeout=3600)
            self.context.test_data.add_result('deploy_android_bootfs_in_master_image',
                                              'pass')
        except:
            msg = 'Master Image Error: unable to deploy android boot filesystem'
            logging.error(msg)
            self.context.test_data.add_result('deploy_android_bootfs_in_master_image',
                                              'fail')
            raise

    def _deploy_linaro_rootfs(self, session, rootfs, rootfstype):
        try:
            logging.info("Deploying linaro image")
            session.run('udevadm trigger')
            session.run('mkdir -p /mnt/root')
            session.run('mount %s /mnt/root' % self.testrootfs_path)
            _test_filesystem_writeable(session, '/mnt/root')
            # The timeout has to be this long for vexpress. For a full desktop it
            # takes 214 minutes, plus about 25 minutes for the mkfs ext3, add
            # another hour to err on the side of caution.
            session._client.target_extract(session, rootfs, '/mnt/root', timeout=18000)

            # DO NOT REMOVE - diverting flash-kernel and linking it to /bin/true
            # prevents a serious problem where packages getting installed that
            # call flash-kernel can update the kernel on the master image
            if session.run('chroot /mnt/root which dpkg-divert', failok=True) == 0:
                session.run(
                    'chroot /mnt/root dpkg-divert --local /usr/sbin/flash-kernel')
                session.run(
                    'chroot /mnt/root ln -sf /bin/true /usr/sbin/flash-kernel')
            # Rewrite fstab file if it exists in test image with the labeled
            # boot/rootfs partitions.
            if session.is_file_exist('/mnt/root/etc/fstab'):
                logging.info("Rewriting /etc/fstab in test image")
                session.run(
                    'echo "LABEL=%s /boot vfat defaults 0 0" > /mnt/root/etc/fstab' %
                    self.testboot_label)
                session.run(
                    'echo "LABEL=%s / %s defaults 0 1" >> /mnt/root/etc/fstab' %
                    (self.testrootfs_label, rootfstype))

            session.run('umount /mnt/root', timeout=3600)
            self.context.test_data.add_result('deploy_rootfs_in_master_image',
                                              'pass')
        except:
            msg = 'Master Image Error: unable to deploy test root filesystem'
            logging.error(msg)
            self.context.test_data.add_result('deploy_rootfs_in_master_image',
                                              'fail')
            raise

    def _deploy_linaro_android_system(self, session, systemtbz2):
        try:
            logging.info("Deploying the Android system fs")
            target = session._client

            session.run('mkdir -p /mnt/lava/system')
            session.run('mount %s /mnt/lava/system' % self.testrootfs_path)
            _test_filesystem_writeable(session, '/mnt/lava/system')
            # Timeout has to be this long because of older vexpress motherboards
            # being somewhat slower
            session._client.target_extract(
                session, systemtbz2, '/mnt/lava', timeout=3600)

            if session.has_partition_with_label(self.userdata_label) and \
               session.has_partition_with_label(self.sdcard_label) and \
               session.is_file_exist('/mnt/lava/system/etc/vold.fstab'):
                # If there is no userdata partition on the sdcard(like iMX and Origen),
                # then the sdcard partition will be used as the userdata partition as
                # before, and so cannot be used here as the sdcard on android
                original = 'dev_mount sdcard %s %s ' % (
                    target.config.sdcard_mountpoint_path,
                    target.config.sdcard_part_android_org)
                replacement = 'dev_mount sdcard %s %s ' % (
                    target.config.sdcard_mountpoint_path,
                    target.config.sdcard_part_android)
                sed_cmd = "s@{original}@{replacement}@".format(original=original,
                                                               replacement=replacement)
                session.run(
                    'sed -i "%s" /mnt/lava/system/etc/vold.fstab' % sed_cmd,
                    failok=True)
                session.run("cat /mnt/lava/system/etc/vold.fstab", failok=True)

            script_path = '%s/%s' % ('/mnt/lava', '/system/bin/disablesuspend.sh')
            if not session.is_file_exist(script_path):
                session.run("sh -c 'export http_proxy=%s'" %
                            target.context.config.lava_proxy)
                session.run('wget --no-check-certificate %s -O %s' %
                            (target.config.git_url_disablesuspend_sh, script_path))
                session.run('chmod +x %s' % script_path)
                session.run('chown :2000 %s' % script_path)

            session.run("""sed -i '/export HOME/i \
                        PS1="%s"
                        ' /mnt/lava/system/etc/mkshrc""" % target.tester_ps1,
                        failok=True)
            session.run('cat /mnt/lava/system/etc/mkshrc', failok=True)

            session.run('umount /mnt/lava/system', timeout=3600)
            self.context.test_data.add_result('deploy_android_systemfs_in_master_image',
                                              'pass')
        except:
            msg = 'Master Image Error: unable to deploy android system filesystem'
            logging.error(msg)
            self.context.test_data.add_result('deploy_android_systemfs_in_master_image',
                                              'fail')
            raise

    def _purge_linaro_android_sdcard(self, session):
        try:
            logging.info("Reformatting Linaro Android sdcard filesystem")
            session.run('nice mkfs.vfat %s -n %s' % (self.sdcard_path, self.sdcard_label))
            session.run('udevadm trigger')
            session.run('mkdir /tmp/sdcard; mount %s /tmp/sdcard' % self.sdcard_path)
            _test_filesystem_writeable(session, '/tmp/sdcard')
            session.run('umount /tmp/sdcard; rm -r /tmp/sdcard', timeout=3600)
            self.context.test_data.add_result('format_sdcard_partition_in_master_image',
                                              'pass')
        except:
            msg = 'Master Image Error: unable to format Android sdcard partition'
            logging.error(msg)
            self.context.test_data.add_result('format_sdcard_partition_in_master_image',
                                              'fail')
            raise

target_class = MasterImageTarget


class MasterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the master image.
    """

    def __init__(self, target):
        super(MasterCommandRunner, self).__init__(
            target, target.MASTER_PS1_PATTERN, prompt_str_includes_rc=True)

    def get_device_version(self):
        pattern = 'device_version=(\d+-\d+/\d+-\d+)'
        self.run("echo \"device_version="
                 "$(lava-master-image-info --master-image-hwpack "
                 "| sed 's/[^0-9-]//g; s/^-\+//')"
                 "/"
                 "$(lava-master-image-info --master-image-rootfs "
                 "| sed 's/[^0-9-]//g; s/^-\+//')"
                 "\"",
                 [pattern, pexpect.EOF, pexpect.TIMEOUT],
                 timeout=5)

        device_version = None
        if self.match_id == 0:
            device_version = self.match.group(1)
            logging.debug('Master image version (hwpack/rootfs) is %s', device_version)
        else:
            logging.warning('Could not determine image version!')

        return device_version

    def has_partition_with_label(self, label):
        if not label:
            return False

        path = '/dev/disk/by-label/%s' % label
        return self.is_file_exist(path)

    def is_file_exist(self, path):
        cmd = 'ls %s > /dev/null' % path
        rc = self.run(cmd, failok=True)
        if rc == 0:
            return True
        return False


def _extract_partition(image, partno, tarfile):
    """Mount a partition and produce a tarball of it

    :param image: The image to mount
    :param partno: The index of the partition in the image
    :param tarfile: path and filename of the tgz to output
    """
    with image_partition_mounted(image, partno) as mntdir:
        mk_targz(tarfile, mntdir, asroot=True)


def _update_ramdisk_partitions(session, rc_filename):
    # Original android sdcard partition layout by l-a-m-c
    sys_part_org = session._client.config.sys_part_android_org
    cache_part_org = session._client.config.cache_part_android_org
    data_part_org = session._client.config.data_part_android_org
    partition_padding_string_org = session._client.config.partition_padding_string_org

    # Sdcard layout in Lava image
    sys_part_lava = session._client.config.sys_part_android
    data_part_lava = session._client.config.data_part_android
    partition_padding_string_lava = session._client.config.partition_padding_string_android

    blkorg = session._client.config.android_orig_block_device
    blklava = session._client.config.android_lava_block_device

    # delete use of cache partition
    session.run('sed -i "/\/dev\/block\/%s%s%s/d" %s'
                % (blkorg, partition_padding_string_org, cache_part_org, rc_filename))
    session.run('sed -i "s/%s%s%s/%s%s%s/g" %s' % (blkorg, partition_padding_string_org, data_part_org, blklava,
                                                   partition_padding_string_lava, data_part_lava, rc_filename))
    session.run('sed -i "s/%s%s%s/%s%s%s/g" %s' % (blkorg, partition_padding_string_org, sys_part_org, blklava,
                                                   partition_padding_string_lava, sys_part_lava, rc_filename))


def _recreate_ramdisk(session, target):
    logging.debug("Recreate Ramdisk")

    ramdisk_name = None
    is_uboot = False

    session.run('mkdir -p ~/tmp/')
    for ramdisk in target.config.android_ramdisk_files:
        rc = session.run('mv /mnt/lava/boot/%s ~/tmp/' % ramdisk, failok=True)
        if rc == 0:
            ramdisk_name = ramdisk
            break

    if ramdisk_name is None:
        raise CriticalError("No valid ramdisk found!")

    session.run('cd ~/tmp/')

    rc = session.run('file %s | grep u-boot' % ramdisk_name, failok=True)

    if rc == 0:
        logging.info("U-Boot Header Detected")
        is_uboot = True
        session.run('nice dd if=%s of=ramdisk.cpio.gz ibs=64 skip=1' % ramdisk_name)
    else:
        session.run('mv %s ramdisk.cpio.gz' % ramdisk_name)

    session.run('nice gzip -d -f ramdisk.cpio.gz; cpio -i -F ramdisk.cpio')

    for init in target.config.android_init_files:
        rc = session.run('test -f %s' % init, failok=True)
        if rc == 0:
            session.run(
                'sed -i "/export PATH/a \ \ \ \ export PS1 \'%s\'" %s' %
                (target.tester_ps1, init))

    # The mount partitions have moved from init.rc to init.partitions.rc
    # For backward compatible with early android build, we update both rc files
    # For omapzoom and aosp and JB4.2 the operation for mounting partitions are
    # in init.omap4pandaboard.rc and fstab.* files
    possible_partitions_files = session._client.config.possible_partitions_files

    for f in possible_partitions_files:
        if session.is_file_exist(f):
            _update_ramdisk_partitions(session, f)
            session.run("cat %s" % f, failok=True)

    session.run('nice cpio -i -t -F ramdisk.cpio | cpio -o -H newc | \
            gzip > ramdisk_new.cpio.gz')

    if is_uboot:
        session.run(
            'nice mkimage -A arm -O linux -T ramdisk -n "Android Ramdisk Image" \
                -d ramdisk_new.cpio.gz %s' % ramdisk_name)
    else:
        session.run('mv ramdisk_new.cpio.gz %s' % ramdisk_name)

    session.run('cd -')
    session.run('mv ~/tmp/%s /mnt/lava/boot/%s' % (ramdisk_name, ramdisk_name))
    session.run('rm -rf ~/tmp')


def _test_filesystem_writeable(runner, mountpoint):
    logging.debug("Checking if filesystem %s is writeable", mountpoint)
    current_time = int(time.time())
    m = hashlib.md5()
    m.update(str(current_time))
    md5sum = m.hexdigest()
    logging.debug("writing %s to ddout, md5sum %s", current_time, md5sum)
    write_res = runner.run('echo -n %s | dd oflag=direct,sync of=%s/ddout ' % (current_time, mountpoint), failok=True)
    if write_res > 0:
        raise RuntimeError('Failed to write test data to %s (sd card writeable test)' % mountpoint)
    else:
        read_res = runner.run('dd if=%s/ddout iflag=direct | md5sum | grep %s' % (mountpoint, md5sum), failok=True)
        if read_res > 0:
            raise RuntimeError('Filesystem %s was not writeable (bad sd card?)' % mountpoint)
    runner.run('rm %s/ddout' % mountpoint, failok=True)
