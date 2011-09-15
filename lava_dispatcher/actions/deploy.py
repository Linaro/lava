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
# along with this program; if not, see <http://www.gnu.org/licenses>.

from commands import getoutput, getstatusoutput
import os
import sys
import re
import shutil
import traceback
from tempfile import mkdtemp

from lava_dispatcher.actions import BaseAction
from lava_dispatcher.utils import download, download_with_cache
from lava_dispatcher.client import CriticalError


class cmd_deploy_linaro_image(BaseAction):
    def run(self, hwpack, rootfs, kernel_matrix=None, use_cache=True):
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        LAVA_IMAGE_URL = self.context.lava_image_url
        client = self.client
        print "deploying on %s" % client.hostname
        print "  hwpack: %s" % hwpack
        print "  rootfs: %s" % rootfs
        if kernel_matrix:
            print "  package: %s" % kernel_matrix[0]
        print "Booting master image"
        client.boot_master_image()

        print "Waiting for network to come up"
        try:
            client.wait_network_up()
        except:
            tb = traceback.format_exc()
            client.sio.write(tb)
            raise CriticalError("Unable to reach LAVA server, check network")

        if kernel_matrix:
            hwpack = self.refresh_hwpack(kernel_matrix, hwpack, use_cache)
            #make new hwpack downloadable
            hwpack = hwpack.replace(LAVA_IMAGE_TMPDIR, '')
            hwpack = '/'.join(u.strip('/') for u in [
                LAVA_IMAGE_URL, hwpack])
            print "  hwpack with new kernel: %s" % hwpack

        try:
            boot_tgz, root_tgz = self.generate_tarballs(hwpack, rootfs, 
                use_cache)
        except:
            tb = traceback.format_exc()
            client.sio.write(tb)
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
            tb = traceback.format_exc()
            client.sio.write(tb)
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
        cmd = "sudo mount -o loop,offset=%s %s %s" % (offset, image, mntdir)
        rc, output = getstatusoutput(cmd)
        if rc:
            os.rmdir(mntdir)
            raise RuntimeError("Unable to mount image %s at offset %s" % (
                image, offset))
        cmd = "sudo tar -C %s -czf %s ." % (mntdir, tarfile)
        rc, output = getstatusoutput(cmd)
        if rc:
            error_msg = "Failed to create tarball: %s" % tarfile
        cmd = "sudo umount %s" % mntdir
        rc, output = getstatusoutput(cmd)
        os.rmdir(mntdir)
        if error_msg:
            raise RuntimeError(error_msg)

    def generate_tarballs(self, hwpack_url, rootfs_url, use_cache=True):
        """Generate tarballs from a hwpack and rootfs url

        :param hwpack_url: url of the Linaro hwpack to download
        :param rootfs_url: url of the Linaro image to download
        """
        lava_cachedir = self.context.lava_cachedir
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        client = self.client
        self.tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        tarball_dir = self.tarball_dir
        os.chmod(tarball_dir, 0755)
        #fix me: if url is not http-prefix, copy it to tarball_dir
        if use_cache:
            hwpack_path = download_with_cache(hwpack_url, tarball_dir, lava_cachedir)
            rootfs_path = download_with_cache(rootfs_url, tarball_dir, lava_cachedir)
        else:
            hwpack_path = download(hwpack_url, tarball_dir)
            rootfs_path = download(rootfs_url, tarball_dir)

        image_file = os.path.join(tarball_dir, "lava.img")
        cmd = ("sudo linaro-media-create --hwpack-force-yes --dev %s "
               "--image_file %s --binary %s --hwpack %s --image_size 3G" %
               (client.device_type, image_file, rootfs_path, hwpack_path))
        rc, output = getstatusoutput(cmd)
        if rc:
            shutil.rmtree(tarball_dir)
            tb = traceback.format_exc()
            client.sio.write(tb)
            raise RuntimeError("linaro-media-create failed: %s" % output)
        boot_offset = self._get_partition_offset(image_file, client.boot_part)
        root_offset = self._get_partition_offset(image_file, client.root_part)
        boot_tgz = os.path.join(tarball_dir, "boot.tgz")
        root_tgz = os.path.join(tarball_dir, "root.tgz")
        try:
            self._extract_partition(image_file, boot_offset, boot_tgz)
            self._extract_partition(image_file, root_offset, root_tgz)
        except:
            shutil.rmtree(tarball_dir)
            tb = traceback.format_exc()
            client.sio.write(tb)
            raise
        return boot_tgz, root_tgz

    def deploy_linaro_rootfs(self, rootfs):
        client = self.client
        print "Deploying linaro image"
        client.run_cmd_master('umount /dev/disk/by-label/testrootfs')
        client.run_cmd_master(
            'mkfs.ext3 -q /dev/disk/by-label/testrootfs -L testrootfs')
        client.run_cmd_master('udevadm trigger')
        client.run_cmd_master('mkdir -p /mnt/root')
        client.run_cmd_master('mount /dev/disk/by-label/testrootfs /mnt/root')
        client.run_cmd_master(
            'wget -qO- %s |tar --numeric-owner -C /mnt/root -xzf -' % rootfs,
            timeout=3600)
        client.run_cmd_master('echo linaro > /mnt/root/etc/hostname')
        #DO NOT REMOVE - diverting flash-kernel and linking it to /bin/true
        #prevents a serious problem where packages getting installed that
        #call flash-kernel can update the kernel on the master image
        client.run_cmd_master(
            'chroot /mnt/root dpkg-divert --local /usr/sbin/flash-kernel')
        client.run_cmd_master(
            'chroot /mnt/root ln -sf /bin/true /usr/sbin/flash-kernel')
        client.run_cmd_master('umount /mnt/root')

    def deploy_linaro_bootfs(self, bootfs):
        client = self.client
        client.run_cmd_master('umount /dev/disk/by-label/testboot')
        client.run_cmd_master(
            'mkfs.vfat /dev/disk/by-label/testboot -n testboot')
        client.run_cmd_master('udevadm trigger')
        client.run_cmd_master('mkdir -p /mnt/boot')
        client.run_cmd_master('mount /dev/disk/by-label/testboot /mnt/boot')
        client.run_cmd_master(
            'wget -qO- %s |tar --numeric-owner -C /mnt/boot -xzf -' % bootfs)
        client.run_cmd_master('umount /mnt/boot')

    def refresh_hwpack(self, kernel_matrix, hwpack, use_cache=True):
        client = self.client
        lava_cachedir = self.context.lava_cachedir
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        print "Deploying new kernel"
        new_kernel = kernel_matrix[0]
        deb_prefix = kernel_matrix[1]
        filesuffix = new_kernel.split(".")[-1]

        if filesuffix != "deb":
            raise CriticalError("New kernel only support deb kernel package!")

        # download package to local
        tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        os.chmod(tarball_dir, 0755)
        if use_cache:
            kernel_path = download_with_cache(new_kernel, tarball_dir, lava_cachedir)
            hwpack_path = download_with_cache(hwpack, tarball_dir, lava_cachedir)
        else:
            kernel_path = download(new_kernel, tarball_dir)
            hwpack_path = download(hwpack, tarball_dir)

        cmd = ("sudo linaro-hwpack-replace -t %s -p %s -r %s" 
                % (hwpack_path, kernel_path, deb_prefix))

        rc, output = getstatusoutput(cmd)
        if rc:
            shutil.rmtree(tarball_dir)
            tb = traceback.format_exc()
            client.sio.write(tb)
            raise RuntimeError("linaro-hwpack-replace failed: %s" % output)

        #fix it:l-h-r doesn't make a output option to specify the output hwpack,
        #so it needs to do manually here

        #remove old hwpack and leave only new hwpack in tarball_dir
        os.remove(hwpack_path)
        hwpack_list = os.listdir(tarball_dir)
        for hp in hwpack_list:
            if hp.split(".")[-1] == "gz":
                new_hwpack_path = os.path.join(tarball_dir, hp)
                return new_hwpack_path

