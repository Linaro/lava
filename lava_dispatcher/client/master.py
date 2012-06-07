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
import re
import shutil
import subprocess
from tempfile import mkdtemp
import time
import traceback
import atexit

import pexpect
import errno

from lava_dispatcher.utils import (
    download,
    logging_spawn,
    logging_system,
    string_to_list,
    url_to_cache, link_or_copy_file)
from lava_dispatcher.client.base import (
    CommandRunner,
    CriticalError,
    LavaClient,
    NetworkCommandRunner,
    OperationFailed,
    )
from lava_dispatcher.client.lmc_utils import (
    generate_image,
    image_partition_mounted,
    )


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

WGET_DEBUGGING_OPTIONS='-S --progress=dot -e dotbytes=2M'

def _deploy_tarball_to_board(session, tarball_url, dest, timeout=-1, num_retry=2):
    decompression_char = ''
    if tarball_url.endswith('.gz') or tarball_url.endswith('.tgz'):
        decompression_char = 'z'
    elif tarball_url.endswith('.bz2'):
        decompression_char = 'j'

    deploy_ok = False

    while num_retry > 0:
        try:
            session.run(
                'wget --no-proxy --connect-timeout=30 %s -O- %s |'
                'tar --numeric-owner -C %s -x%sf -'
                % (WGET_DEBUGGING_OPTIONS, tarball_url, dest, decompression_char),
                timeout=timeout)
        except (OperationFailed, pexpect.TIMEOUT):
            logging.warning("Deploy %s failed. %d retry left." %(tarball_url, num_retry-1))
        else:
            deploy_ok = True
            break

        if num_retry > 1:
            # send CTRL C in case wget still hasn't exited.
            session._client.proc.sendcontrol("c")
            session._client.proc.sendline("echo 'retry left %s'" % (num_retry-1))
            # And wait a little while.
            sleep_time=5*60
            logging.info("Wait %d second before retry" % sleep_time)
            time.sleep(sleep_time)
        num_retry = num_retry - 1

    if not deploy_ok:
        raise Exception("Deploy tarball (%s) to board failed" % tarball_url);

def _deploy_linaro_rootfs(session, rootfs):
    logging.info("Deploying linaro image")
    session.run('udevadm trigger')
    session.run('mkdir -p /mnt/root')
    session.run('mount /dev/disk/by-label/testrootfs /mnt/root')
    # The timeout has to be this long for vexpress. For a full desktop it
    # takes 214 minutes, plus about 25 minutes for the mkfs ext3, add
    # another hour to err on the side of caution.
    _deploy_tarball_to_board(session, rootfs, '/mnt/root', timeout=18000)

    session.run('echo linaro > /mnt/root/etc/hostname')
    #DO NOT REMOVE - diverting flash-kernel and linking it to /bin/true
    #prevents a serious problem where packages getting installed that
    #call flash-kernel can update the kernel on the master image
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
    _deploy_tarball_to_board(session, bootfs, '/mnt/boot')
    session.run('umount /mnt/boot')

def _deploy_linaro_android_testboot(session, boottbz2, pkgbz2=None):
    logging.info("Deploying test boot filesystem")
    session.run('umount /dev/disk/by-label/testboot', failok=True)
    session.run('mkfs.vfat /dev/disk/by-label/testboot '
                          '-n testboot')
    session.run('udevadm trigger')
    session.run('mkdir -p /mnt/lava/boot')
    session.run('mount /dev/disk/by-label/testboot '
                          '/mnt/lava/boot')
    _deploy_tarball_to_board(session, boottbz2, '/mnt/lava')
    if pkgbz2:
        _deploy_tarball_to_board(session, pkgbz2, '/mnt/lava')

    _recreate_uInitrd(session)

def _update_uInitrd_partitions(session, rc_filename):
    # Original android sdcard partition layout by l-a-m-c
    sys_part_org = session._client.device_option("sys_part_android_org")
    cache_part_org = session._client.device_option("cache_part_android_org")
    data_part_org = session._client.device_option("data_part_android_org")
    # Sdcard layout in Lava image
    sys_part_lava = session._client.device_option("sys_part_android")
    data_part_lava = session._client.device_option("data_part_android")

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

def _recreate_uInitrd(session):
    logging.debug("Recreate uInitrd")

    session.run('mkdir -p ~/tmp/')
    session.run('mv /mnt/lava/boot/uInitrd ~/tmp')
    session.run('cd ~/tmp/')

    session.run('dd if=uInitrd of=uInitrd.data ibs=64 skip=1')
    session.run('mv uInitrd.data ramdisk.cpio.gz')
    session.run(
        'gzip -d -f ramdisk.cpio.gz; cpio -i -F ramdisk.cpio')

    # The mount partitions have moved from init.rc to init.partitions.rc
    # For backward compatible with early android build, we updatep both rc files
    _update_uInitrd_partitions(session, 'init.rc')
    _update_uInitrd_partitions(session, 'init.partitions.rc')

    session.run(
        'sed -i "/export PATH/a \ \ \ \ export PS1 root@linaro: " init.rc')

    session.run("cat init.rc")
    session.run("cat init.partitions.rc", failok=True)

    session.run(
        'cpio -i -t -F ramdisk.cpio | cpio -o -H newc | \
            gzip > ramdisk_new.cpio.gz')

    session.run(
        'mkimage -A arm -O linux -T ramdisk -n "Android Ramdisk Image" \
            -d ramdisk_new.cpio.gz uInitrd')

    session.run('cd -')
    session.run('mv ~/tmp/uInitrd /mnt/lava/boot/uInitrd')
    session.run('rm -rf ~/tmp')

def _deploy_linaro_android_testrootfs(session, systemtbz2, rootfstype):
    logging.info("Deploying the test root filesystem")
#    sdcard_part_lava = session._client.device_option("sdcard_part_android")

    session.run('umount /dev/disk/by-label/testrootfs', failok=True)
    session.run(
        'mkfs -t %s -q /dev/disk/by-label/testrootfs -L testrootfs' % rootfstype, timeout=1800)
    session.run('udevadm trigger')
    session.run('mkdir -p /mnt/lava/system')
    session.run(
        'mount /dev/disk/by-label/testrootfs /mnt/lava/system')
    _deploy_tarball_to_board(session, systemtbz2, '/mnt/lava', timeout=600)

#    sed_cmd = "/dev_mount sdcard \/mnt\/sdcard/c dev_mount sdcard /mnt/sdcard %s " \
#        "/devices/platform/omap/omap_hsmmc.0/mmc_host/mmc0" % sdcard_part_lava
#    session.run(
#        'sed -i "%s" /mnt/lava/system/etc/vold.fstab' % sed_cmd)
    session.run(
        'sed -i "s/^PS1=.*$/PS1=\'root@linaro: \'/" /mnt/lava/system/etc/mkshrc',
        failok=True)
    session.run('umount /mnt/lava/system')

def _purge_linaro_android_sdcard(session):
    logging.info("Reformatting Linaro Android sdcard filesystem")
    session.run('mkfs.vfat /dev/disk/by-label/sdcard -n sdcard')
    session.run('udevadm trigger')

def _deploy_linaro_android_data(session, datatbz2):
    ##consider the compatiblity, here use the existed sdcard partition
    data_label = 'sdcard'
    session.run('umount /dev/disk/by-label/%s' % data_label, failok=True)
    session.run('mkfs.ext4 -q /dev/disk/by-label/%s -L %s' % (data_label, data_label))
    session.run('udevadm trigger')
    session.run('mkdir -p /mnt/lava/data')
    session.run('mount /dev/disk/by-label/%s /mnt/lava/data' % (data_label))
    _deploy_tarball_to_board(session, datatbz2, '/mnt/lava', timeout=600)
    session.run('umount /mnt/lava/data')

class PrefixCommandRunner(CommandRunner):
    """A CommandRunner that prefixes every command run with a given string.

    The motivating use case is to prefix every command with 'chroot
    $LOCATION'.
    """

    def __init__(self, prefix, connection, prompt_str):
        super(PrefixCommandRunner, self).__init__(connection, prompt_str)
        if not prefix.endswith(' '):
            prefix += ' '
        self._prefix = prefix

    def run(self, cmd, response=None, timeout=-1, failok=False):
        return super(PrefixCommandRunner, self).run(
            self._prefix + cmd, response, timeout, failok)


class MasterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the master image.

    See `LavaClient.master_session`.
    """

    def __init__(self, client):
        super(MasterCommandRunner, self).__init__(client, client.master_str)

    def get_master_ip(self):
        #get master image ip address
        try:
            self.wait_network_up()
        except:
            logging.warning(traceback.format_exc())
            return None
        #tty device uses minimal match, see pexpect wiki
        pattern1 = "<(\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?)>"
        cmd = ("ifconfig %s | grep 'inet addr' | awk -F: '{print $2}' |"
                "awk '{print \"<\" $1 \">\"}'" % self._client.default_network_interface)
        self.run(
            cmd, [pattern1, pexpect.EOF, pexpect.TIMEOUT], timeout=5)
        if self.match_id == 0:
            ip = self.match.group(1)
            logging.debug("Master image IP is %s" % ip)
            return ip
        return None


class LavaMasterImageClient(LavaClient):

    def __init__(self, context, config):
        super(LavaMasterImageClient, self).__init__(context, config)
        pre_connect = self.device_option("pre_connect_command")
        if pre_connect:
            logging_system(pre_connect)
        self.proc = self._connect_carefully()
        atexit.register(self._close_logging_spawn)

    def _connect_carefully(self):
        cmd = self.device_option("connection_command")

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
            #serial can be slow, races do funny things if you don't increase delay
            proc.delaybeforesend=1
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
                reset_port = self.device_option("reset_port_command")
                if reset_port:
                    logging_system(reset_port)
                else:
                    raise OperationFailed("no reset_port command configured")
                proc.close(True)
                retry_count += 1
                time.sleep(5)
        raise OperationFailed("could execute connection_command successfully")

    @property
    def master_str(self):
        return self.device_option("MASTER_STR")

    def _close_logging_spawn(self):
        self.proc.close(True)

    def decompress(self, image_file):
        for suffix, command in [('.gz', 'gunzip'),
                                ('.xz', 'unxz'),
                                ('.bz2', 'bunzip2')]:
            if image_file.endswith(suffix):
                logging.info("Uncompressing %s with %s", image_file, command)
                uncompressed_name = image_file[:-len(suffix)]
                subprocess.check_call(
                    [command, '-c', image_file], stdout=open(uncompressed_name, 'w'))
                return uncompressed_name
        return image_file

    def _tarball_url_to_cache(self, url, cachedir):
        cache_loc = url_to_cache(url, cachedir)
        # can't have a folder name same as file name. replacing '.' with '.'
        return os.path.join(cache_loc.replace('.','-'), "tarballs")

    def _are_tarballs_cached(self, image, lava_cachedir):
        cache_loc = self._tarball_url_to_cache(image, lava_cachedir)
        cached = os.path.exists(os.path.join(cache_loc, "boot.tgz")) and \
               os.path.exists(os.path.join(cache_loc, "root.tgz"))

        if cached:
            return True;

        # Check if there is an other lava-dispatch instance have start to cache the same image
        # see the _about_to_cache_tarballs
        if not os.path.exists(os.path.join(cache_loc, "tarballs-cache-ongoing")):
            return False

        # wait x minute for caching is done.
        waittime=20

        logging.info("Waiting for the other instance of lava-dispatcher to finish the caching of %s", image)
        while waittime > 0:
            if not os.path.exists(os.path.join(cache_loc, "tarballs-cache-ongoing")):
                waittime = 0
            else:
                time.sleep(60)
                waittime = waittime - 1
                if (waittime % 5) == 0:
                    logging.info("%d minute left..." % waittime)

        return os.path.exists(os.path.join(cache_loc, "boot.tgz")) and \
               os.path.exists(os.path.join(cache_loc, "root.tgz"))

    def _get_cached_tarballs(self, image, tarball_dir, lava_cachedir):
        cache_loc = self._tarball_url_to_cache(image, lava_cachedir)

        boot_tgz = os.path.join(tarball_dir,"boot.tgz")
        root_tgz = os.path.join(tarball_dir,"root.tgz")
        link_or_copy_file(os.path.join(cache_loc, "root.tgz"), root_tgz)
        link_or_copy_file(os.path.join(cache_loc, "boot.tgz"), boot_tgz)

        return (boot_tgz,root_tgz)

    def _about_to_cache_tarballs(self, image, lava_cachedir):
        # create this folder to indicate this instance of lava-dispatcher is caching this image.
        # see _are_tarballs_cached
        # return false if unable to create the directory. The caller should not cache the tarballs
        cache_loc = self._tarball_url_to_cache(image, lava_cachedir)
        path = os.path.join(cache_loc, "tarballs-cache-ongoing")
        try:
          os.makedirs(path)
        except OSError as exc: # Python >2.5
            if exc.errno == errno.EEXIST:
                # other dispatcher process already caching - concurrency issue
                return False
            else:
                raise
        return True

    def _cache_tarballs(self, image, boot_tgz, root_tgz, lava_cachedir):
        cache_loc = self._tarball_url_to_cache(image, lava_cachedir)
        if not os.path.exists(cache_loc):
              os.makedirs(cache_loc)
        c_boot_tgz = os.path.join(cache_loc, "boot.tgz")
        c_root_tgz = os.path.join(cache_loc, "root.tgz")
        shutil.copy(boot_tgz, c_boot_tgz)
        shutil.copy(root_tgz, c_root_tgz)
        path = os.path.join(cache_loc, "tarballs-cache-ongoing")
        if os.path.exists(path):
            shutil.rmtree(path)

    def _download(self, url, directory):
        lava_cookies = self.context.lava_cookies
        return download(url, directory, lava_proxy)

    def deploy_linaro(self, hwpack=None, rootfs=None, image=None,
                      kernel_matrix=None, use_cache=True, rootfstype='ext3'):
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        LAVA_IMAGE_URL = self.context.lava_image_url
        # validate in parameters
        if image is None:
            if hwpack is None or rootfs is None:
                raise CriticalError(
                    "must specify both hwpack and rootfs when not specifying image")
        else:
            if hwpack is not None or rootfs is not None or kernel_matrix is not None:
                raise CriticalError(
                        "cannot specify hwpack or rootfs when specifying image")

        # generate image if needed
        try:
            if image is None:
                image_file = generate_image(self, hwpack, rootfs, kernel_matrix, use_cache)
                boot_tgz, root_tgz = self._generate_tarballs(image_file)
            else:
                tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
                os.chmod(tarball_dir, 0755)
                if use_cache:
                    lava_cachedir = self.context.lava_cachedir
                    if self._are_tarballs_cached(image, lava_cachedir):
                        logging.info("Reusing cached tarballs")
                        boot_tgz, root_tgz = self._get_cached_tarballs(image, tarball_dir, lava_cachedir)
                    else:
                        logging.info("Downloading and caching the tarballs")
                        # in some corner case, there can be more than one lava-dispatchers execute
                        # caching of same tarballs exact at the same time. One of them will successfully
                        # get the lock directory. The rest will skip the caching if _about_to_cache_tarballs
                        # return false.
                        should_cache = self._about_to_cache_tarballs(image, lava_cachedir)
                        image_file = self._download(image, tarball_dir)
                        image_file = self.decompress(image_file)
                        boot_tgz, root_tgz = self._generate_tarballs(image_file)
                        if should_cache:
                            self._cache_tarballs(image, boot_tgz, root_tgz, lava_cachedir)
                else:
                    image_file = self._download(image, tarball_dir)
                    image_file = self.decompress(image_file)
                    boot_tgz, root_tgz = self._generate_tarballs(image_file)
                    # remove the cached tarballs
                    cache_loc = self._tarball_url_to_cache(image, lava_cachedir)
                    shutil.rmtree(cache_loc, ignore_errors = true)
                    # remove the cached image files
                    cache_loc = url_to_cache
                    shutil.rmtree(cache_loc, ignore_errors = true)

        except CriticalError:
            raise
        except:
            logging.error("Deployment tarballs preparation failed")
            tb = traceback.format_exc()
            self.sio.write(tb)
            raise CriticalError("Deployment tarballs preparation failed")

        # deploy the boot image and rootfs to target
        logging.info("Booting master image")
        try:
            self.boot_master_image()
            boot_tarball = boot_tgz.replace(LAVA_IMAGE_TMPDIR, '')
            root_tarball = root_tgz.replace(LAVA_IMAGE_TMPDIR, '')
            boot_url = '/'.join(u.strip('/') for u in [
                LAVA_IMAGE_URL, boot_tarball])
            root_url = '/'.join(u.strip('/') for u in [
                LAVA_IMAGE_URL, root_tarball])
            with self._master_session() as session:
                self._format_testpartition(session, rootfstype)

                logging.info("Waiting for network to come up")
                try:
                    session.wait_network_up()
                except:
                    logging.error("Unable to reach LAVA server, check network")
                    tb = traceback.format_exc()
                    self.sio.write(tb)
                    raise CriticalError("Unable to reach LAVA server, check network")

                try:
                    _deploy_linaro_rootfs(session, root_url)
                    _deploy_linaro_bootfs(session, boot_url)
                except:
                    logging.error("Deployment failed")
                    tb = traceback.format_exc()
                    self.sio.write(tb)
                    raise CriticalError("Deployment failed")
        finally:
            shutil.rmtree(os.path.dirname(boot_tgz))

    def deploy_linaro_android(self, boot, system, data, pkg=None, use_cache=True, rootfstype='ext4'):
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        LAVA_IMAGE_URL = self.context.lava_image_url
        logging.info("Deploying Android on %s" % self.hostname)
        logging.info("  boot: %s" % boot)
        logging.info("  system: %s" % system)
        logging.info("  data: %s" % data)
        logging.info("Boot master image")
        try:
            self.boot_master_image()
            with self._master_session() as session:
                logging.info("Waiting for network to come up...")
                try:
                    session.wait_network_up()
                except:
                    logging.error("Unable to reach LAVA server, check network")
                    tb = traceback.format_exc()
                    self.sio.write(tb)
                    raise CriticalError("Unable to reach LAVA server, check network")

                try:
                    boot_tbz2, system_tbz2, data_tbz2, pkg_tbz2 = \
                        self._download_tarballs(boot, system, data, pkg, use_cache)
                except:
                    logging.error("Unable to download artifacts for deployment")
                    tb = traceback.format_exc()
                    self.sio.write(tb)
                    raise CriticalError("Unable to download artifacts for deployment")

                boot_tarball = boot_tbz2.replace(LAVA_IMAGE_TMPDIR, '')
                system_tarball = system_tbz2.replace(LAVA_IMAGE_TMPDIR, '')
                data_tarball = data_tbz2.replace(LAVA_IMAGE_TMPDIR, '')

                boot_url = '/'.join(u.strip('/') for u in [
                    LAVA_IMAGE_URL, boot_tarball])
                system_url = '/'.join(u.strip('/') for u in [
                    LAVA_IMAGE_URL, system_tarball])
                data_url = '/'.join(u.strip('/') for u in [
                    LAVA_IMAGE_URL, data_tarball])

                if pkg_tbz2:
                    pkg_tarball = pkg_tbz2.replace(LAVA_IMAGE_TMPDIR, '')
                    pkg_url = '/'.join(u.strip('/') for u in [
                        LAVA_IMAGE_URL, pkg_tarball])
                else:
                    pkg_url = None

                try:
                    _deploy_linaro_android_testboot(session, boot_url, pkg_url)
                    _deploy_linaro_android_testrootfs(session, system_url, rootfstype)
#                    _purge_linaro_android_sdcard(session)
                    _deploy_linaro_android_data(session, data_url)
                except:
                    logging.error("Android deployment failed")
                    tb = traceback.format_exc()
                    self.sio.write(tb)
                    raise CriticalError("Android deployment failed")
        finally:
            shutil.rmtree(self.tarball_dir)
            logging.info("Android image deployment exiting")

    def _download_tarballs(self, boot_url, system_url, data_url, pkg_url=None,
            use_cache=True):
        """Download tarballs from a boot, system and data tarball url

        :param boot_url: url of the Linaro Android boot tarball to download
        :param system_url: url of the Linaro Android system tarball to download
        :param data_url: url of the Linaro Android data tarball to download
        :param pkg_url: url of the custom kernel tarball to download
        :param use_cache: whether or not to use the cached copy (if it exists)
        """
        lava_proxy = self.context.lava_proxy
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        self.tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        tarball_dir = self.tarball_dir
        os.chmod(tarball_dir, 0755)
        logging.info("Downloading the image files")

        proxy = lava_proxy if use_cache else None

        boot_path = download(boot_url, tarball_dir, proxy)
        system_path = download(system_url, tarball_dir, proxy)
        data_path = download(data_url, tarball_dir, proxy)
        if pkg_url:
            pkg_path = download(pkg_url, tarball_dir, proxy)
        else:
            pkg_path = None
        logging.info("Downloaded the image files")
        return  boot_path, system_path, data_path, pkg_path

    def boot_master_image(self):
        """
        reboot the system, and check that we are in a master shell
        """
        logging.info("Boot the system master image")
        try:
            self.soft_reboot()
            image_boot_msg = self.device_option('image_boot_msg')
            self.proc.expect(image_boot_msg, timeout=300)
            self._in_master_shell(300)
        except:
            logging.exception("in_master_shell failed")
            self.hard_reboot()
            image_boot_msg = self.device_option('image_boot_msg')
            self.proc.expect(image_boot_msg, timeout=300)
            self._in_master_shell(300)
        self.proc.sendline('export PS1="$PS1 [rc=$(echo \$?)]: "')
        self.proc.expect(self.master_str, timeout=120, lava_no_logging=1)
        self.setup_proxy(self.master_str)
        logging.info("System is in master image now")

    def _format_testpartition(self, session, fstype):
        logging.info("Format testboot and testrootfs partitions")
        session.run('umount /dev/disk/by-label/testrootfs', failok=True)
        session.run(
            'mkfs -t %s -q /dev/disk/by-label/testrootfs -L testrootfs'
            % fstype, timeout=1800)
        session.run('umount /dev/disk/by-label/testboot', failok=True)
        session.run('mkfs.vfat /dev/disk/by-label/testboot -n testboot')

    def _generate_tarballs(self, image_file):
        """Generate tarballs from a hwpack and rootfs url

        :param hwpack_url: url of the Linaro hwpack to download
        :param rootfs_url: url of the Linaro image to download
        """
        tarball_dir = os.path.dirname(image_file)
        boot_tgz = os.path.join(tarball_dir, "boot.tgz")
        root_tgz = os.path.join(tarball_dir, "root.tgz")
        try:
            _extract_partition(image_file, self.boot_part, boot_tgz)
            _extract_partition(image_file, self.root_part, root_tgz)
        except:
            logging.error("Failed to generate tarballs")
            shutil.rmtree(tarball_dir)
            tb = traceback.format_exc()
            self.sio.write(tb)
            raise
        return boot_tgz, root_tgz

    def reliable_session(self):
        return self._partition_session('testrootfs')

    def retrieve_results(self, result_disk):
        with self._master_session() as session:

            session.run('mkdir -p /mnt/root')
            session.run(
                'mount /dev/disk/by-label/%s /mnt/root' % result_disk)
            # Clean results directory on master image
            session.run(
                'rm -rf /tmp/lava_results.tgz /tmp/%s' % self.context.lava_result_dir)
            session.run('mkdir -p /tmp/%s' % self.context.lava_result_dir)
            session.run(
                'cp /mnt/root/%s/*.bundle /tmp/%s' % (self.context.lava_result_dir,
                    self.context.lava_result_dir))
            # Clean result bundle on test image
            session.run(
                'rm -f /mnt/root/%s/*.bundle' % (self.context.lava_result_dir))
            session.run('umount /mnt/root')

            # Create tarball of all results
            logging.info("Creating lava results tarball")
            session.run('cd /tmp')
            session.run(
                'tar czf /tmp/lava_results.tgz -C /tmp/%s .' % self.context.lava_result_dir)

            # start gather_result job, status
            err_msg = ''
            master_ip = session.get_master_ip()
            if not master_ip:
                err_msg = (err_msg + "Getting master image IP address failed, "
                           "no test case result retrieved.")
                logging.warning(err_msg)
                return 'fail', err_msg, None
            # Set 80 as server port
            session.run('python -m SimpleHTTPServer 80 &> /dev/null &')
            try:
                time.sleep(3)

                result_tarball = "http://%s/lava_results.tgz" % master_ip
                tarball_dir = mkdtemp(dir=self.context.lava_image_tmpdir)
                os.chmod(tarball_dir, 0755)

                # download test result with a retry mechanism
                # set retry timeout to 5 mins
                logging.info("About to download the result tarball to host")
                now = time.time()
                timeout = 300
                tries = 0

                while True:
                    try:
                        result_path = download(result_tarball, tarball_dir)
                        return 'pass', '', result_path
                    except RuntimeError:
                        tries += 1
                        if time.time() >= now + timeout:
                            logging.error(
                                "download '%s' failed. Nr tries = %s" % (
                                    result_tarball, tries))
                            return 'fail', err_msg, None
                        else:
                            logging.info(
                                "Sleep one minute and retry (%d)" % tries)
                            time.sleep(60)
            finally:
                session.run('kill %1')
                session.run('')


    @contextlib.contextmanager
    def _partition_session(self, partition):
        """A session that can be used to run commands in a given test
        partition.

        Anything that uses this will have to be done differently for images
        that are not deployed via a master image (e.g. using a JTAG to blow
        the image onto the card or testing under QEMU).
        """
        with self._master_session() as master_session:
            directory = '/mnt/' + partition
            master_session.run('mkdir -p %s' % directory)
            master_session.run('mount /dev/disk/by-label/%s %s' % (
                partition, directory))
            master_session.run(
                'cp -f %s/etc/resolv.conf %s/etc/resolv.conf.bak' % (
                    directory, directory))
            master_session.run('cp -L /etc/resolv.conf %s/etc' % directory)
            #eliminate warning: Can not write log, openpty() failed
            #                   (/dev/pts not mounted?), does not work
            master_session.run('mount --rbind /dev %s/dev' % directory)
            try:
                yield PrefixCommandRunner(
                    'chroot ' + directory, self.proc, self.master_str)
            finally:
                master_session.run(
                    'cp -f %s/etc/resolv.conf.bak %s/etc/resolv.conf' % (
                        directory, directory))
                cmd = ('cat /proc/mounts | awk \'{print $2}\' | grep "^%s/dev"'
                       '| sort -r | xargs umount' % directory)
                master_session.run(cmd)
                master_session.run('umount ' + directory)

    def _in_master_shell(self, timeout=10):
        """
        Check that we are in a shell on the master image
        """
        self.proc.sendline("")
        match_id = self.proc.expect(
            [self.master_str, pexpect.TIMEOUT], timeout=timeout, lava_no_logging=1)
        if match_id == 1:
            raise OperationFailed

    @contextlib.contextmanager
    def _master_session(self):
        """A session that can be used to run commands in the master image.

        Anything that uses this will have to be done differently for images
        that are not deployed via a master image (e.g. using a JTAG to blow
        the image onto the card or testing under QEMU).
        """
        try:
            self._in_master_shell()
        except OperationFailed:
            self.boot_master_image()
        yield MasterCommandRunner(self)

    def soft_reboot(self):
        logging.info("Perform soft reboot the system")
        cmd = self.device_option("soft_boot_cmd")
        # make sure in the shell (sometime the earlier command has not exit) by sending CTRL + C
        self.proc.sendline("\003")
        if cmd != "":
            self.proc.sendline(cmd)
        else:
            self.proc.sendline("reboot")
        # Looking for reboot messages or if they are missing, the U-Boot message will also indicate the
        # reboot is done.
        id = self.proc.expect(
            ['Restarting system.', 'The system is going down for reboot NOW',
                'Will now restart', 'U-Boot', pexpect.TIMEOUT], timeout=120)
        if id not in [0, 1, 2, 3]:
            raise Exception("Soft reboot failed")

    def hard_reboot(self):
        logging.info("Perform hard reset on the system")
        cmd = self.device_option("hard_reset_command", "")
        if cmd != "":
            logging_system(cmd)
        else:
            self.proc.send("~$")
            self.proc.sendline("hardreset")
        # after hardreset empty the pexpect buffer
        self._empty_pexpect_buffer()

    def _empty_pexpect_buffer(self):
        """Make sure there is nothing in the pexpect buffer."""
        index = 0
        while index == 0:
            index = self.proc.expect(
                ['.+', pexpect.EOF, pexpect.TIMEOUT], timeout=1, lava_no_logging=1)

    def _enter_uboot(self):
        interrupt_boot_prompt = self.device_option('interrupt_boot_prompt')
        self.proc.expect(interrupt_boot_prompt)

        interrupt_boot_command = self.device_option('interrupt_boot_command')
        self.proc.sendline(interrupt_boot_command)

    def _boot_linaro_image(self):
        self._boot(string_to_list(self.config.get('boot_cmds')))

    def _boot_linaro_android_image(self):
        self._boot(string_to_list(self.config.get('boot_cmds_android')))

    def _boot(self, boot_cmds):
        try:
            self.soft_reboot()
            self._enter_uboot()
        except:
            logging.exception("_enter_uboot failed")
            self.hard_reboot()
            self._enter_uboot()
        self.proc.sendline(boot_cmds[0])
        bootloader_prompt = re.escape(self.device_option('bootloader_prompt'))
        for line in range(1, len(boot_cmds)):
            self.proc.expect(bootloader_prompt, timeout=300)
            self.proc.sendline(boot_cmds[line])
