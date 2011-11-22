# Copyright (C) 2011 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
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
import contextlib
import logging
import os
import pexpect
import re
import shutil
from tempfile import mkdtemp
import traceback

from lava_dispatcher.client import (
    CommandRunner,
    LavaClient,
    )
from lava_dispatcher.utils import download, download_with_cache


class LavaQEMUClient(LavaClient):

    def deploy_linaro(self, hwpack, rootfs, kernel_matrix=None, use_cache=True):
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        LAVA_IMAGE_URL = self.context.lava_image_url
        logging.info("'deploying' on %s" % self.hostname)
        logging.info("  hwpack: %s" % hwpack)
        logging.info("  rootfs: %s" % rootfs)
        if kernel_matrix:
            logging.info("  package: %s" % kernel_matrix[0])
            hwpack = self._refresh_hwpack(kernel_matrix, hwpack, use_cache)
            #make new hwpack downloadable
            hwpack = hwpack.replace(LAVA_IMAGE_TMPDIR, '')
            hwpack = '/'.join(u.strip('/') for u in [
                LAVA_IMAGE_URL, hwpack])
            logging.info("  hwpack with new kernel: %s" % hwpack)

        #image_file = self._generate_image(hwpack, rootfs, use_cache)
        self.context.action_data['image_location'] = '/tmp/lava.img'

    def _generate_image(self, hwpack_url, rootfs_url, use_cache=True):
        """Generate image from a hwpack and rootfs url

        :param hwpack_url: url of the Linaro hwpack to download
        :param rootfs_url: url of the Linaro image to download
        """
        lava_cachedir = self.context.lava_cachedir
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        self.tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        tarball_dir = self.tarball_dir
        os.chmod(tarball_dir, 0755)
        #fix me: if url is not http-prefix, copy it to tarball_dir
        if use_cache:
            logging.info("Downloading the %s file using cache" % hwpack_url)
            hwpack_path = download_with_cache(hwpack_url, tarball_dir, lava_cachedir)

            logging.info("Downloading the %s file using cache" % rootfs_url)
            rootfs_path = download_with_cache(rootfs_url, tarball_dir, lava_cachedir)
        else:
            logging.info("Downloading the %s file" % hwpack_url)
            hwpack_path = download(hwpack_url, tarball_dir)

            logging.info("Downloading the %s file" % rootfs_url)
            rootfs_path = download(rootfs_url, tarball_dir)

        logging.info("linaro-media-create version information")
        cmd = "sudo linaro-media-create -v"
        rc, output = getstatusoutput(cmd)
        metadata = self.context.test_data.get_metadata()
        metadata['target.linaro-media-create-version'] = output
        self.context.test_data.add_metadata(metadata)

        image_file = os.path.join(tarball_dir, "lava.img")
        #XXX Hack for removing startupfiles from snowball hwpacks
        if self.device_type == "snowball_sd":
            cmd = "sudo linaro-hwpack-replace -r startupfiles-v3 -t %s -i" % hwpack_path
            rc, output = getstatusoutput(cmd)
            if rc:
                raise RuntimeError("linaro-hwpack-replace failed: %s" % output)

        cmd = ("sudo flock /var/lock/lava-lmc.lck linaro-media-create --hwpack-force-yes --dev %s "
               "--image-file %s --binary %s --hwpack %s --image-size 3G" %
               (self.lmc_dev_arg, image_file, rootfs_path, hwpack_path))
        logging.info("Executing the linaro-media-create command")
        logging.info(cmd)
        rc, output = getstatusoutput(cmd)
        if rc:
            shutil.rmtree(tarball_dir)
            tb = traceback.format_exc()
            self.sio.write(tb)
            raise RuntimeError("linaro-media-create failed: %s" % output)
        return image_file

    def _get_partition_offset(self, image, partno):
        cmd = 'parted %s -m -s unit b print' % image
        part_data = getoutput(cmd)
        pattern = re.compile('%d:([0-9]+)B:' % partno)
        for line in part_data.splitlines():
            found = re.match(pattern, line)
            if found:
                return found.group(1)
        return None

    @contextlib.contextmanager
    def reliable_session(self):
        def system(cmd):
            logging.info('executing %r'%cmd)
            os.system(cmd)
        mntdir = mkdtemp()
        image = self.context.action_data['image_location']
        offset = self._get_partition_offset(image, self.root_part)
        mount_cmd = "sudo mount -o loop,offset=%s %s %s" % (offset, image, mntdir)
        rc = system(mount_cmd)
        if rc:
            os.rmdir(mntdir)
            raise RuntimeError("Unable to mount image %s at offset %s" % (
                image, offset))
        try:
            system('sudo cp %s/etc/resolv.conf %s/etc/resolv.conf.bak' % (mntdir, mntdir))
            system('sudo cp %s/etc/hosts %s/etc/hosts.bak' % (mntdir, mntdir))
            system('sudo cp /etc/hosts %s/etc/hosts' % (mntdir,))
            system('sudo cp /etc/resolv.conf %s/etc/resolv.conf' % (mntdir,))
            system('sudo cp /usr/bin/qemu-arm-static %s/usr/bin/' % (mntdir,))

            cmd = pexpect.spawn('chroot ' + mntdir, logfile=self.sio)
            try:
                cmd.sendline("export PS1='root@host-mount:# '")
                cmd.expect('root@host-mount:#')
                yield CommandRunner(cmd, 'root@host-mount:#')
            finally:
                system('sudo mv %s/etc/resolv.conf.bak %s/etc/resolv.conf' % (mntdir, mntdir))
                system('sudo mv %s/etc/hosts.bak %s/etc/hosts' % (mntdir, mntdir))
                system('sudo rm %s/usr/bin/qemu-arm-static' % (mntdir,))
                cmd.close()
        finally:
            os.system('sudo umount ' + mntdir)
            os.rmdir(mntdir)
