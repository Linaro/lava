# Copyright (C) 2011 Linaro Limited
#
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

from commands import getoutput, getstatusoutput
import os
import re
import shutil
from tempfile import mkdtemp

from lava_dispatcher.actions import BaseAction
from lava_dispatcher.config import LAVA_IMAGE_TMPDIR, LAVA_IMAGE_URL, MASTER_STR
from lava_dispatcher.utils import download, download_with_cache
from lava_dispatcher.client import CriticalError


class cmd_deploy_linaro_image(BaseAction):
    def run(self, hwpack, rootfs, use_cache=True):
        client = self.client
        print "deploying on %s" % client.hostname
        print "  hwpack: %s" % hwpack
        print "  rootfs: %s" % rootfs
        print "Booting master image"
        client.boot_master_image()

        print "Waiting for network to come up"
        try:
            client.wait_network_up()
        except:
            raise CriticalError("Network can't probe up when deployment")

        try:
            boot_tgz, root_tgz = self.generate_tarballs(hwpack, rootfs, 
                use_cache)
        except:
            raise CriticalError("Deployment tarballs preparation failed")
        boot_tarball = boot_tgz.replace(LAVA_IMAGE_TMPDIR, '')
        root_tarball = root_tgz.replace(LAVA_IMAGE_TMPDIR, '')
        boot_url = '/'.join(u.strip('/') for u in [
            LAVA_IMAGE_URL, boot_tarball])
        root_url = '/'.join(u.strip('/') for u in [
            LAVA_IMAGE_URL, root_tarball])
        try:
            self.deploy_linaro_rootfs(root_url)
            self.deploy_linaro_bootfs(boot_url)
        except:
            raise CriticalError("Deployment failed")
        finally:
            shutil.rmtree(self.tarball_dir)

    def _get_partition_offset(self, image, partno):
        cmd = 'parted %s -m -s unit b print' % image
        part_data = getoutput(cmd)
        pattern = re.compile('%d:([0-9]+)B:' % partno)
        for line in part_data.splitlines():
            found = re.match(pattern, line)
            if found:
                return found.group(1)
        return None

    def _extract_partition(self, image, offset, tarfile):
        """Mount a partition and produce a tarball of it

        :param image: The image to mount
        :param offset: offset of the partition, as a string
        :param tarfile: path and filename of the tgz to output
        """
        error_msg = None
        mntdir = mkdtemp()
        cmd = "mount -o loop,offset=%s %s %s" % (offset, image, mntdir)
        rc, output = getstatusoutput(cmd)
        if rc:
            os.rmdir(mntdir)
            raise RuntimeError("Unable to mount image %s at offset %s" % (
                image, offset))
        cmd = "tar -C %s -czf %s ." % (mntdir, tarfile)
        rc, output = getstatusoutput(cmd)
        if rc:
            error_msg = "Failed to create tarball: %s" % tarfile
        cmd = "umount %s" % mntdir
        rc, output = getstatusoutput(cmd)
        os.rmdir(mntdir)
        if error_msg:
            raise RuntimeError(error_msg)

    def generate_tarballs(self, hwpack_url, rootfs_url, use_cache=True):
        """Generate tarballs from a hwpack and rootfs url

        :param hwpack_url: url of the Linaro hwpack to download
        :param rootfs_url: url of the Linaro image to download
        """
        client = self.client
        self.tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        tarball_dir = self.tarball_dir
        os.chmod(tarball_dir, 0755)
        if use_cache:
            hwpack_path = download_with_cache(hwpack_url, tarball_dir)
            rootfs_path = download_with_cache(rootfs_url, tarball_dir)
        else:
            hwpack_path = download(hwpack_url, tarball_dir)
            rootfs_path = download(rootfs_url, tarball_dir)

        image_file = os.path.join(tarball_dir, "lava.img")
        board = client.board
        cmd = ("linaro-media-create --hwpack-force-yes --dev %s "
               "--image_file %s --binary %s --hwpack %s" % (
                board.type, image_file, rootfs_path, hwpack_path))
        rc, output = getstatusoutput(cmd)
        if rc:
            shutil.rmtree(tarball_dir)
            raise RuntimeError("linaro-media-create failed: %s" % output)
        boot_offset = self._get_partition_offset(image_file, board.boot_part)
        root_offset = self._get_partition_offset(image_file, board.root_part)
        boot_tgz = os.path.join(tarball_dir, "boot.tgz")
        root_tgz = os.path.join(tarball_dir, "root.tgz")
        try:
            self._extract_partition(image_file, boot_offset, boot_tgz)
            self._extract_partition(image_file, root_offset, root_tgz)
        except:
            shutil.rmtree(tarball_dir)
            raise
        return boot_tgz, root_tgz

    def deploy_linaro_rootfs(self, rootfs):
        client = self.client
        print "Deploying linaro image"
        client.run_shell_command(
            'mkfs.ext3 -q /dev/disk/by-label/testrootfs -L testrootfs',
            response = MASTER_STR)
        client.run_shell_command(
            'udevadm trigger',
            response = MASTER_STR)
        client.run_shell_command(
            'mkdir -p /mnt/root',
            response = MASTER_STR)
        client.run_shell_command(
            'mount /dev/disk/by-label/testrootfs /mnt/root',
            response = MASTER_STR)
        client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/root -xzf -' % rootfs,
            response = MASTER_STR, timeout = 3600)
        client.run_shell_command(
            'echo linaro > /mnt/root/etc/hostname',
            response = MASTER_STR)
        client.run_shell_command(
            'umount /mnt/root',
            response = MASTER_STR)

    def deploy_linaro_bootfs(self, bootfs):
        client = self.client
        client.run_shell_command(
            'mkfs.vfat /dev/disk/by-label/testboot -n testboot',
            response = MASTER_STR)
        client.run_shell_command(
            'udevadm trigger',
            response = MASTER_STR)
        client.run_shell_command(
            'mkdir -p /mnt/boot',
            response = MASTER_STR)
        client.run_shell_command(
            'mount /dev/disk/by-label/testboot /mnt/boot',
            response = MASTER_STR)
        client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/boot -xzf -' % bootfs,
            response = MASTER_STR)
        client.run_shell_command(
            'umount /mnt/boot',
            response = MASTER_STR)

