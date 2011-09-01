#!/usr/bin/python

# Copyright (C) 2011 Linaro Limited
#
# Author: Linaro Validation Team <linaro-dev@lists.linaro.org>
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
# along with this program; if not, see <http://www.gnu.org/licenses>.

from lava_dispatcher.actions import BaseAction
import os
import sys
import shutil
import traceback
from tempfile import mkdtemp
from lava_dispatcher.utils import download, download_with_cache
from lava_dispatcher.client import CriticalError

class cmd_deploy_linaro_android_image(BaseAction):
    def run(self, boot, system, data, use_cache=True):
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        LAVA_IMAGE_URL = self.context.lava_image_url
        client = self.client
        print "deploying Android on %s" % client.hostname
        print "  boot: %s" % boot
        print "  system: %s" % system
        print "  data: %s" % data
        print "Booting master image"
        client.boot_master_image()

        print "Waiting for network to come up"
        try:
            client.wait_network_up()
        except:
            tb = traceback.format_exc()
            client.sio.write(tb)
            raise CriticalError("Unable to reach LAVA server, check network")

        try:
            boot_tbz2, system_tbz2, data_tbz2 = self.download_tarballs(boot,
                system, data, use_cache)
        except:
            tb = traceback.format_exc()
            client.sio.write(tb)
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

        try:
            self.deploy_linaro_android_testboot(boot_url)
            self.deploy_linaro_android_testrootfs(system_url)
            self.purge_linaro_android_sdcard()
        except:
            tb = traceback.format_exc()
            client.sio.write(tb)
            raise CriticalError("Android deployment failed")
        finally:
            shutil.rmtree(self.tarball_dir)

    def download_tarballs(self, boot_url, system_url, data_url, use_cache=True):
        """Download tarballs from a boot, system and data tarball url

        :param boot_url: url of the Linaro Android boot tarball to download
        :param system_url: url of the Linaro Android system tarball to download
        :param data_url: url of the Linaro Android data tarball to download
        :param use_cache: whether or not to use the cached copy (if it exists)
        """
        lava_cachedir = self.context.lava_cachedir
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        self.tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        tarball_dir = self.tarball_dir
        os.chmod(tarball_dir, 0755)

        if use_cache:
            boot_path = download_with_cache(boot_url, tarball_dir, lava_cachedir)
            system_path = download_with_cache(system_url, tarball_dir, lava_cachedir)
            data_path = download_with_cache(data_url, tarball_dir, lava_cachedir)
        else:
            boot_path = download(boot_url, tarball_dir)
            system_path = download(system_url, tarball_dir)
            data_path = download(data_url, tarball_dir)
        return  boot_path, system_path, data_path

    def deploy_linaro_android_testboot(self, boottbz2):
        client = self.client
        client.run_cmd_master('mkfs.vfat /dev/disk/by-label/testboot '
                              '-n testboot')
        client.run_cmd_master('udevadm trigger')
        client.run_cmd_master('mkdir -p /mnt/lava/boot')
        client.run_cmd_master('mount /dev/disk/by-label/testboot '
                              '/mnt/lava/boot')
        client.run_cmd_master('wget -qO- %s |tar --numeric-owner -C /mnt/lava -xjf -' % boottbz2)

        self.recreate_uInitrd()

        client.run_cmd_master('umount /mnt/lava/boot')

    def recreate_uInitrd(self):
        client = self.client
        client.run_cmd_master('mkdir -p ~/tmp/')
        client.run_cmd_master('mv /mnt/lava/boot/uInitrd ~/tmp')
        client.run_cmd_master('cd ~/tmp/')
        client.run_cmd_master('dd if=uInitrd of=uInitrd.data ibs=64 skip=1')
        client.run_cmd_master('mv uInitrd.data ramdisk.cpio.gz')
        client.run_cmd_master(
            'gzip -d ramdisk.cpio.gz; cpio -i -F ramdisk.cpio')
        client.run_cmd_master(
            'sed -i "/mount ext4 \/dev\/block\/mmcblk0p3/d" init.rc')
        client.run_cmd_master(
            'sed -i "/mount ext4 \/dev\/block\/mmcblk0p5/d" init.rc')
        client.run_cmd_master('sed -i "s/mmcblk0p2/mmcblk0p5/g" init.rc')
        client.run_cmd_master(
            'sed -i "/export PATH/a \ \ \ \ export PS1 root@linaro: " init.rc')

        client.run_cmd_master(
            'cpio -i -t -F ramdisk.cpio | cpio -o -H newc | \
                gzip > ramdisk_new.cpio.gz')

        client.run_cmd_master(
            'mkimage -A arm -O linux -T ramdisk -n "Android Ramdisk Image" \
                -d ramdisk_new.cpio.gz uInitrd')

        client.run_cmd_master('cd -')
        client.run_cmd_master('mv ~/tmp/uInitrd /mnt/lava/boot/uInitrd')
        client.run_cmd_master('rm -rf ~/tmp')

    def deploy_linaro_android_testrootfs(self, systemtbz2):
        client = self.client
        client.run_cmd_master(
            'mkfs.ext4 -q /dev/disk/by-label/testrootfs -L testrootfs')
        client.run_cmd_master('udevadm trigger')
        client.run_cmd_master('mkdir -p /mnt/lava/system')
        client.run_cmd_master(
            'mount /dev/disk/by-label/testrootfs /mnt/lava/system')
        client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/lava -xjf -' % systemtbz2,
            client.master_str, 600)

        sed_cmd = "/dev_mount sdcard \/mnt\/sdcard/c dev_mount sdcard /mnt/sdcard 6 " \
            "/devices/platform/omap/omap_hsmmc.0/mmc_host/mmc0"
        client.run_cmd_master(
            'sed -i "%s" /mnt/lava/system/etc/vold.fstab' % sed_cmd)
        client.run_cmd_master('umount /mnt/lava/system')

    def purge_linaro_android_sdcard(self):
        client = self.client
        client.run_cmd_master('mkfs.vfat /dev/disk/by-label/sdcard -n sdcard')
        client.run_cmd_master('udevadm trigger')

    def deploy_linaro_android_system(self, systemtbz2):
        client = self.client
        client.run_cmd_master('mkfs.ext4 -q /dev/disk/by-label/system -L system')
        client.run_cmd_master('udevadm trigger')
        client.run_cmd_master('mkdir -p /mnt/lava/system')
        client.run_cmd_master('mount /dev/disk/by-label/system /mnt/lava/system')
        client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/lava -xjf -' % systemtbz2,
            client.master_str, 600)
        client.run_cmd_master('umount /mnt/lava/system')

    def deploy_linaro_android_data(self, datatbz2):
        client = self.client
        client.run_cmd_master('mkfs.ext4 -q /dev/disk/by-label/data -L data')
        client.run_cmd_master('udevadm trigger')
        client.run_cmd_master('mkdir -p /mnt/lava/data')
        client.run_cmd_master('mount /dev/disk/by-label/data /mnt/lava/data')
        client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/lava -xjf -' % datatbz2,
            client.master_str, 600)
        client.run_cmd_master('umount /mnt/lava/data')
