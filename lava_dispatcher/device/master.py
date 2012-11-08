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

import atexit
import contextlib
import logging
import os
import shutil
import time
import traceback

import pexpect

import lava_dispatcher.tarballcache as tarballcache

from lava_dispatcher.device.target import (
    Target
    )
from lava_dispatcher.downloader import (
    download_image,
    download_with_retry,
    )
from lava_dispatcher.utils import (
    logging_spawn,
    logging_system,
    string_to_list,
    )
from lava_dispatcher.client.base import (
    NetworkError,
    CriticalError,
    NetworkCommandRunner,
    OperationFailed,
    )
from lava_dispatcher.client.lmc_utils import (
    generate_image,
    image_partition_mounted,
    )


class MasterImageTarget(Target):

    MASTER_PS1 = 'root@master [rc=$(echo \$?)]# '
    MASTER_PS1_PATTERN = 'root@master \[rc=(\d+)\]# '

    def __init__(self, context, config):
        super(MasterImageTarget, self).__init__(context, config)

        Target.android_deployment_data['boot_cmds'] = 'boot_cmds_android'
        Target.ubuntu_deployment_data['boot_cmds'] = 'boot_cmds'

        # used for tarballcache logic to get proper boot_cmds
        Target.ubuntu_deployment_data['data_type'] = 'ubuntu'
        Target.oe_deployment_data['data_type'] = 'oe'
        self.target_map = {
            'android': Target.android_deployment_data,
            'oe': Target.oe_deployment_data,
            'ubuntu': Target.ubuntu_deployment_data,
            }

        self.master_ip = None

        if config.pre_connect_command:
            logging_system(config.pre_connect_command)

        self.proc = self._connect_carefully(config.connection_command)
        atexit.register(self._close_logging_spawn)

    def power_on(self):
        self._boot_linaro_image()
        return self.proc

    def _power_off(self, proc):
        # we always leave master image devices powered on
        pass

    def deploy_linaro(self, hwpack, rfs):
        self.boot_master_image()

        image_file = generate_image(self, hwpack, rfs, self.scratch_dir)
        (boot_tgz, root_tgz, data) = self._generate_tarballs(image_file)

        self._deploy_tarballs(boot_tgz, root_tgz)

    def deploy_android(self, boot, system, userdata):
        self.boot_master_image()

        sdir = self.scratch_dir
        boot = download_image(boot, self.context, sdir, decompress=False)
        system = download_image(system, self.context, sdir, decompress=False)
        data = download_image(userdata, self.context, sdir, decompress=False)

        tmpdir = self.context.config.lava_image_tmpdir
        url = self.context.config.lava_image_url

        boot = boot.replace(tmpdir, '')
        system = system.replace(tmpdir, '')
        data = data.replace(tmpdir, '')

        boot_url = '/'.join(u.strip('/') for u in [url, boot])
        system_url = '/'.join(u.strip('/') for u in [url, system])
        data_url = '/'.join(u.strip('/') for u in [url, data])

        with self._as_master() as master:
            self._format_testpartition(master, 'ext4')
            _deploy_linaro_android_boot(master, boot_url, self)
            _deploy_linaro_android_system(master, system_url)
            _deploy_linaro_android_data(master, data_url)

            if master.has_partition_with_label('userdata') and \
                   master.has_partition_with_label('sdcard'):
                _purge_linaro_android_sdcard(master)

        self.deployment_data = Target.android_deployment_data

    def deploy_linaro_prebuilt(self, image):
        self.boot_master_image()

        if self.context.job_data.get('health_check', False):
            (boot_tgz, root_tgz, data) = tarballcache.get_tarballs(
                self.context, image, self.scratch_dir, self._generate_tarballs)
            self.deployment_data = self.target_map[data]
        else:
            image_file = download_image(image, self.context, self.scratch_dir)
            (boot_tgz, root_tgz, data) = self._generate_tarballs(image_file)

        self._deploy_tarballs(boot_tgz, root_tgz)

    def _deploy_tarballs(self, boot_tgz, root_tgz):
        tmpdir = self.context.config.lava_image_tmpdir
        url = self.context.config.lava_image_url

        boot_tarball = boot_tgz.replace(tmpdir, '')
        root_tarball = root_tgz.replace(tmpdir, '')
        boot_url = '/'.join(u.strip('/') for u in [url, boot_tarball])
        root_url = '/'.join(u.strip('/') for u in [url, root_tarball])
        with self._as_master() as master:
            self._format_testpartition(master, 'ext4')
            try:
                _deploy_linaro_rootfs(master, root_url)
                _deploy_linaro_bootfs(master, boot_url)
            except:
                logging.error("Deployment failed")
                tb = traceback.format_exc()
                self.sio.write(tb)
                raise CriticalError("Deployment failed")

    def _format_testpartition(self, runner, fstype):
        logging.info("Format testboot and testrootfs partitions")
        runner.run('umount /dev/disk/by-label/testrootfs', failok=True)
        runner.run('mkfs -t %s -q /dev/disk/by-label/testrootfs -L testrootfs'
            % fstype, timeout=1800)
        runner.run('umount /dev/disk/by-label/testboot', failok=True)
        runner.run('mkfs.vfat /dev/disk/by-label/testboot -n testboot')

    def _generate_tarballs(self, image_file):
        self._customize_linux(image_file)
        boot_tgz = os.path.join(self.scratch_dir, "boot.tgz")
        root_tgz = os.path.join(self.scratch_dir, "root.tgz")
        try:
            _extract_partition(image_file, self.config.boot_part, boot_tgz)
            _extract_partition(image_file, self.config.root_part, root_tgz)
        except:
            logging.error("Failed to generate tarballs")
            tb = traceback.format_exc()
            self.sio.write(tb)
            raise

        # we need to associate the deployment data with these so that we
        # can provide the proper boot_cmds later on in the job
        data = self.deployment_data['data_type']
        return boot_tgz, root_tgz, data

    def target_extract(self, runner, tar_url, dest, timeout=-1, num_retry=5):
        decompression_char = ''
        if tar_url.endswith('.gz') or tar_url.endswith('.tgz'):
            decompression_char = 'z'
        elif tar_url.endswith('.bz2'):
            decompression_char = 'j'
        else:
            raise RuntimeError('bad file extension: %s' % tar_url)

        while num_retry > 0:
            try:
                runner.run(
                    'wget --no-check-certificate --no-proxy '
                    '--connect-timeout=30 -S --progress=dot -e dotbytes=2M '
                    '-O- %s | '
                    'tar --warning=no-timestamp --numeric-owner -C %s -x%sf -'
                    % (tar_url, dest, decompression_char),
                    timeout=timeout)
                return
            except (OperationFailed, pexpect.TIMEOUT):
                logging.warning(("transfering %s failed. %d retry left."
                    % (tar_url, num_retry - 1)))

            if num_retry > 1:
                # send CTRL C in case wget still hasn't exited.
                self.proc.sendcontrol("c")
                self.proc.sendline(
                    "echo 'retry left %s time(s)'" % (num_retry - 1))
                # And wait a little while.
                sleep_time = 60
                logging.info("Wait %d second before retry" % sleep_time)
                time.sleep(sleep_time)
            num_retry = num_retry - 1

        raise RuntimeError('extracting %s on target failed' % tar_url)

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        logging.info('attempting to access master filesystem %r:%s' %
            (partition, directory))

        if partition == self.config.boot_part:
            partition = '/dev/disk/by-label/testboot'
        elif partition == self.config.root_part:
            partition = '/dev/disk/by-label/testrootfs'
        elif partition != self.config.data_part_android_org:
            raise RuntimeError(
                'unknown master image partition(%d)' % partition)

        assert directory != '/', "cannot mount entire partition"

        with self._as_master() as runner:
            if partition == self.config.data_part_android_org:
                lbl = _android_data_label(runner)
                partition = '/dev/disk/by-label/%s' % lbl

            runner.run('mount %s /mnt' % partition)
            try:
                targetdir = os.path.join('/mnt/%s' % directory)
                if not runner.is_file_exist(targetdir):
                    runner.run('mkdir %s' % targetdir)

                parent_dir, target_name = os.path.split(targetdir)

                runner.run('tar -czf /tmp/fs.tgz -C %s %s' % (parent_dir, target_name))
                runner.run('cd /tmp')  # need to be in same dir as fs.tgz
                self.proc.sendline('python -m SimpleHTTPServer 0 2>/dev/null')
                match_id = self.proc.expect([
                    'Serving HTTP on 0.0.0.0 port (\d+) \.\.',
                    pexpect.EOF, pexpect.TIMEOUT])
                if match_id != 0:
                    msg = "Unable to start HTTP server on master"
                    logging.error(msg)
                    raise CriticalError(msg)
                port = self.proc.match.groups()[match_id]

                url = "http://%s:%s/fs.tgz" % (self.master_ip, port)
                tf = download_with_retry(
                    self.context, self.scratch_dir, url, False)

                tfdir = os.path.join(self.scratch_dir, str(time.time()))
                try:
                    os.mkdir(tfdir)
                    logging_system('tar -C %s -xzf %s' % (tfdir, tf))
                    yield os.path.join(tfdir, target_name)

                finally:
                    tf = os.path.join(self.scratch_dir, 'fs')
                    tf = shutil.make_archive(tf, 'gztar', tfdir)
                    shutil.rmtree(tfdir)

                    self.proc.sendcontrol('c')  # kill SimpleHTTPServer

                    # get the last 2 parts of tf, ie "scratchdir/tf.tgz"
                    tf = '/'.join(tf.split('/')[-2:])
                    url = '%s/%s' % (self.context.config.lava_image_url, tf)
                    runner.run('rm -rf %s' % targetdir)
                    self.target_extract(runner, url, parent_dir)

            finally:
                    self.proc.sendcontrol('c')  # kill SimpleHTTPServer
                    runner.run('umount /mnt')

    def _connect_carefully(self, cmd):
        retry_count = 0
        retry_limit = 3

        port_stuck_message = 'Data Buffering Suspended\.'
        conn_closed_message = 'Connection closed by foreign host\.'

        expectations = {
            port_stuck_message: 'reset-port',
            'Connected\.\r': 'all-good',
            conn_closed_message: 'retry',
            pexpect.TIMEOUT: 'all-good',
            }
        patterns = []
        results = []
        for pattern, result in expectations.items():
            patterns.append(pattern)
            results.append(result)

        while retry_count < retry_limit:
            proc = logging_spawn(cmd, timeout=1200)
            proc.logfile_read = self.sio
            #serial can be slow, races do funny things, so increase delay
            proc.delaybeforesend = 1
            logging.info('Attempting to connect to device')
            match = proc.expect(patterns, timeout=10)
            result = results[match]
            logging.info('Matched %r which means %s', patterns[match], result)
            if result == 'retry':
                proc.close(True)
                retry_count += 1
                time.sleep(5)
                continue
            elif result == 'all-good':
                return proc
            elif result == 'reset-port':
                reset_port = self.config.reset_port_command
                if reset_port:
                    logging_system(reset_port)
                else:
                    raise OperationFailed("no reset_port command configured")
                proc.close(True)
                retry_count += 1
                time.sleep(5)
        raise OperationFailed("could execute connection_command successfully")

    def _close_logging_spawn(self):
        self.proc.close(True)

    def _wait_for_master_boot(self):
        self.proc.expect(self.config.image_boot_msg, timeout=300)
        self.proc.expect(self.config.master_str, timeout=300)

    def boot_master_image(self):
        """
        reboot the system, and check that we are in a master shell
        """
        attempts = 3
        in_master_image = False
        while (attempts > 0) and (not in_master_image):
            logging.info("Booting the system master image")
            try:
                self._soft_reboot()
                self._wait_for_master_boot()
            except (OperationFailed, pexpect.TIMEOUT) as e:
                logging.info("Soft reboot failed: %s" % e)
                try:
                    self._hard_reboot()
                    self._wait_for_master_boot()
                except (OperationFailed, pexpect.TIMEOUT) as e:
                    msg = "Hard reboot into master image failed: %s" % e
                    logging.warning(msg)
                    attempts = attempts - 1
                    continue

            try:
                self.proc.sendline('export PS1="%s"' % self.MASTER_PS1)
                self.proc.expect(
                    self.MASTER_PS1_PATTERN, timeout=120, lava_no_logging=1)
            except pexpect.TIMEOUT as e:
                msg = "Failed to get command line prompt: " % e
                logging.warning(msg)
                attempts = attempts - 1
                continue

            runner = MasterCommandRunner(self)
            try:
                self.master_ip = runner.get_master_ip()
            except NetworkError as e:
                msg = "Failed to get network up: " % e
                logging.warning(msg)
                attempts = attempts - 1
                continue

            lava_proxy = self.context.config.lava_proxy
            if lava_proxy:
                logging.info("Setting up http proxy")
                runner.run("export http_proxy=%s" % lava_proxy, timeout=30)
            logging.info("System is in master image now")
            in_master_image = True

        if not in_master_image:
            msg = "Could not get master image booted properly"
            logging.critical(msg)
            raise CriticalError(msg)

    @contextlib.contextmanager
    def _as_master(self):
        """A session that can be used to run commands in the master image."""
        self.proc.sendline("")
        match_id = self.proc.expect(
            [self.MASTER_PS1_PATTERN, pexpect.TIMEOUT],
            timeout=10, lava_no_logging=1)
        if match_id == 1:
            self.boot_master_image()
        yield MasterCommandRunner(self)

    def _soft_reboot(self):
        logging.info("Perform soft reboot the system")
        self.master_ip = None
        # Try to C-c the running process, if any.
        self.proc.sendcontrol('c')
        self.proc.sendline(self.config.soft_boot_cmd)
        # Looking for reboot messages or if they are missing, the U-Boot
        # message will also indicate the reboot is done.
        match_id = self.proc.expect(
            [pexpect.TIMEOUT, 'Restarting system.', 'The system is going down for reboot NOW',
             'Will now restart', 'U-Boot'], timeout=120)
        if match_id == 0:
            raise OperationFailed("Soft reboot failed")

    def _hard_reboot(self):
        logging.info("Perform hard reset on the system")
        self.master_ip = None
        if self.config.hard_reset_command != "":
            logging_system(self.config.hard_reset_command)
        else:
            self.proc.send("~$")
            self.proc.sendline("hardreset")
            self.proc.empty_buffer()

    def _enter_uboot(self):
        if self.proc.expect(self.config.interrupt_boot_prompt) != 0:
            raise Exception("Faile to enter uboot")
        self.proc.sendline(self.config.interrupt_boot_command)

    def _boot_linaro_image(self):
        boot_cmds = self.deployment_data['boot_cmds']
        for option in self.boot_options:
            keyval = option.split('=')
            if len(keyval) != 2:
                logging.warn("Invalid boot option format: %s" % option)
            elif keyval[0] != 'boot_cmds':
                logging.warn("Invalid boot option: %s" % keyval[0])
            else:
                boot_cmds = keyval[1].strip()

        boot_cmds = getattr(self.config, boot_cmds)
        self._boot(string_to_list(boot_cmds.encode('ascii')))

    def _boot(self, boot_cmds):
        try:
            self._soft_reboot()
            self._enter_uboot()
        except:
            logging.exception("_enter_uboot failed")
            self._hard_reboot()
            self._enter_uboot()
        self.proc.sendline(boot_cmds[0])
        for line in range(1, len(boot_cmds)):
            self.proc.expect(self.config.bootloader_prompt, timeout=300)
            self.proc.sendline(boot_cmds[line])


target_class = MasterImageTarget


class MasterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the master image.
    """

    def __init__(self, target):
        super(MasterCommandRunner, self).__init__(
            target, target.MASTER_PS1_PATTERN, prompt_str_includes_rc=True)

    def get_master_ip(self):
        logging.info("Waiting for network to come up")
        try:
            self.wait_network_up(timeout=20)
        except NetworkError:
            msg = "Unable to reach LAVA server"
            logging.error(msg)
            self._client.sio.write(traceback.format_exc())
            raise

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
        cmd = "sudo tar -C %s -czf %s ." % (mntdir, tarfile)
        rc = logging_system(cmd)
        if rc:
            raise RuntimeError("Failed to create tarball: %s" % tarfile)


def _deploy_linaro_rootfs(session, rootfs):
    logging.info("Deploying linaro image")
    session.run('udevadm trigger')
    session.run('mkdir -p /mnt/root')
    session.run('mount /dev/disk/by-label/testrootfs /mnt/root')
    # The timeout has to be this long for vexpress. For a full desktop it
    # takes 214 minutes, plus about 25 minutes for the mkfs ext3, add
    # another hour to err on the side of caution.
    session._client.target_extract(session, rootfs, '/mnt/root', timeout=18000)

    #DO NOT REMOVE - diverting flash-kernel and linking it to /bin/true
    #prevents a serious problem where packages getting installed that
    #call flash-kernel can update the kernel on the master image
    if session.run('chroot /mnt/root which dpkg-divert', failok=True) == 0:
        session.run(
            'chroot /mnt/root dpkg-divert --local /usr/sbin/flash-kernel')
    session.run(
        'chroot /mnt/root ln -sf /bin/true /usr/sbin/flash-kernel')
    session.run('umount /mnt/root')


def _deploy_linaro_bootfs(session, bootfs):
    logging.info("Deploying linaro bootfs")
    session.run('udevadm trigger')
    session.run('mkdir -p /mnt/boot')
    session.run('mount /dev/disk/by-label/testboot /mnt/boot')
    session._client.target_extract(session, bootfs, '/mnt/boot')
    session.run('umount /mnt/boot')


def _deploy_linaro_android_boot(session, boottbz2, target):
    logging.info("Deploying test boot filesystem")
    session.run('mkdir -p /mnt/lava/boot')
    session.run('mount /dev/disk/by-label/testboot /mnt/lava/boot')
    session._client.target_extract(session, boottbz2, '/mnt/lava')
    _recreate_uInitrd(session, target)


def _update_uInitrd_partitions(session, rc_filename):
    # Original android sdcard partition layout by l-a-m-c
    sys_part_org = session._client.config.sys_part_android_org
    cache_part_org = session._client.config.cache_part_android_org
    data_part_org = session._client.config.data_part_android_org
    # Sdcard layout in Lava image
    sys_part_lava = session._client.config.sys_part_android
    data_part_lava = session._client.config.data_part_android

    session.run(
        'sed -i "/mount ext4 \/dev\/block\/mmcblk0p%s/d" %s'
        % (cache_part_org, rc_filename), failok=True)

    session.run('sed -i "s/mmcblk0p%s/mmcblk0p%s/g" %s'
        % (data_part_org, data_part_lava, rc_filename), failok=True)
    session.run('sed -i "s/mmcblk0p%s/mmcblk0p%s/g" %s'
        % (sys_part_org, sys_part_lava, rc_filename), failok=True)
    # for snowball the mcvblk1 is used instead of mmcblk0.
    session.run('sed -i "s/mmcblk1p%s/mmcblk1p%s/g" %s'
        % (data_part_org, data_part_lava, rc_filename), failok=True)
    session.run('sed -i "s/mmcblk1p%s/mmcblk1p%s/g" %s'
        % (sys_part_org, sys_part_lava, rc_filename), failok=True)


def _recreate_uInitrd(session, target):
    logging.debug("Recreate uInitrd")

    session.run('mkdir -p ~/tmp/')
    session.run('mv /mnt/lava/boot/uInitrd ~/tmp')
    session.run('cd ~/tmp/')

    session.run('dd if=uInitrd of=uInitrd.data ibs=64 skip=1')
    session.run('mv uInitrd.data ramdisk.cpio.gz')
    session.run('gzip -d -f ramdisk.cpio.gz; cpio -i -F ramdisk.cpio')

    # The mount partitions have moved from init.rc to init.partitions.rc
    # For backward compatible with early android build, we update both rc files
    _update_uInitrd_partitions(session, 'init.rc')
    _update_uInitrd_partitions(session, 'init.partitions.rc')

    session.run(
        'sed -i "/export PATH/a \ \ \ \ export PS1 \'%s\'" init.rc' %
        target.ANDROID_TESTER_PS1)

    session.run("cat init.rc")
    session.run("cat init.partitions.rc", failok=True)

    session.run('cpio -i -t -F ramdisk.cpio | cpio -o -H newc | \
            gzip > ramdisk_new.cpio.gz')

    session.run(
        'mkimage -A arm -O linux -T ramdisk -n "Android Ramdisk Image" \
            -d ramdisk_new.cpio.gz uInitrd')

    session.run('cd -')
    session.run('mv ~/tmp/uInitrd /mnt/lava/boot/uInitrd')
    session.run('rm -rf ~/tmp')


def _deploy_linaro_android_system(session, systemtbz2):
    logging.info("Deploying the system filesystem")
    target = session._client

    session.run('mkdir -p /mnt/lava/system')
    session.run('mount /dev/disk/by-label/testrootfs /mnt/lava/system')
    session._client.target_extract(
        session, systemtbz2, '/mnt/lava', timeout=600)

    if session.has_partition_with_label('userdata') and \
       session.has_partition_with_label('sdcard') and \
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

    session.run(
        ('sed -i "s/^PS1=.*$/PS1=\'%s\'/" '
         '/mnt/lava/system/etc/mkshrc') % target.ANDROID_TESTER_PS1,
        failok=True)

    session.run('umount /mnt/lava/system')


def _purge_linaro_android_sdcard(session):
    logging.info("Reformatting Linaro Android sdcard filesystem")
    session.run('mkfs.vfat /dev/disk/by-label/sdcard -n sdcard')
    session.run('udevadm trigger')


def _android_data_label(session):
    data_label = 'userdata'
    if not session.has_partition_with_label(data_label):
        #consider the compatiblity, here use the existed sdcard partition
        data_label = 'sdcard'
    return data_label


def _deploy_linaro_android_data(session, datatbz2):
    data_label = _android_data_label(session)
    session.run('umount /dev/disk/by-label/%s' % data_label, failok=True)
    session.run('mkfs.ext4 -q /dev/disk/by-label/%s -L %s' %
        (data_label, data_label))
    session.run('udevadm trigger')
    session.run('mkdir -p /mnt/lava/data')
    session.run('mount /dev/disk/by-label/%s /mnt/lava/data' % (data_label))
    session._client.target_extract(session, datatbz2, '/mnt/lava', timeout=600)
    session.run('umount /mnt/lava/data')
