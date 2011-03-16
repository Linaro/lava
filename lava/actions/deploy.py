#!/usr/bin/python
from commands import getoutput, getstatusoutput
from lava.actions import BaseAction
from lava.config import LAVA_IMAGE_TMPDIR
import os
import re
import shutil
from tempfile import mkdtemp
import urllib2
import urlparse

class cmd_deploy_linaro_image(BaseAction):
    def run(self, hwpack, rootfs):
        print "deploying on %s" % self.client.hostname
        print "  hwpack: %s" % hwpack
        print "  rootfs: %s" % rootfs
        print "Booting master image"
        self.client.boot_master_image()

        print "Waiting for network to come up"
        self.client.wait_network_up()
        boot_tgz, root_tgz = self.generate_tarballs(hwpack, rootfs)

    def _get_partition_offset(self, image, partno):
        cmd = 'parted %s -s unit b p' % image
        part_data = getoutput(cmd)
        pattern = re.compile(' %d\s+([0-9]+)' % partno)
        for line in part_data.splitlines():
            found = re.match(pattern, line)
            if found:
                return found.group(1)

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

    def _download(self, url, path=""):
        urlpath = urlparse.urlsplit(url).path
        filename = os.path.basename(urlpath)
        if path:
            filename = os.path.join(path,filename)
        fd = open(filename, "w")
        try:
            response = urllib2.urlopen(urllib2.quote(url, safe=":/"))
            fd = open(filename, 'wb')
            shutil.copyfileobj(response,fd,0x10000)
            fd.close()
            response.close()
        except:
            raise RuntimeError("Could not retrieve %s" % url)
        return filename

    def generate_tarballs(self, hwpack_url, rootfs_url):
        """Generate tarballs from a hwpack and rootfs url

        :param hwpack_url: url of the Linaro hwpack to download
        :param rootfs_url: url of the Linaro image to download
        """
        tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        hwpack_path = self._download(hwpack_url, tarball_dir)
        rootfs_path = self._download(rootfs_url, tarball_dir)
        image_file = os.path.join(tarball_dir, "lava.img")
        cmd = ("linaro-media-create --hwpack-force-yes --dev %s "
               "--image_file %s --binary %s --hwpack %s" % (
                self.client.board.type, image_file, rootfs_path,
                hwpack_path))
        rc, output = getstatusoutput(cmd)
        if rc:
            shutil.rmtree(tarball_dir)
            raise RuntimeError("linaro-media-create failed: %s" % output)
        #mx51evk has a different partition layout
        if self.client.board.type == "mx51evk":
            boot_offset = self._get_partition_offset(image_file, 2)
            root_offset = self._get_partition_offset(image_file, 3)
        else:
            boot_offset = self._get_partition_offset(image_file, 1)
            root_offset = self._get_partition_offset(image_file, 2)
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
        print "Deploying linaro image"
        master_str = 'root@master:'
        self.client.run_shell_command(
            'mkfs.ext3 -q /dev/disk/by-label/testrootfs -L testrootfs',
            response = master_str)
        self.client.run_shell_command(
            'udevadm trigger',
            response = master_str)
        self.client.run_shell_command(
            'mkdir -p /mnt/root',
            response = master_str)
        self.client.run_shell_command(
            'mount /dev/disk/by-label/testrootfs /mnt/root',
            response = master_str)
        self.client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/root -xzf -' % rootfs,
            response = master_str, timeout = 600)
        self.client.run_shell_command(
            'umount /mnt/root',
            response = master_str)

    def deploy_linaro_bootfs(self, bootfs):
        master_str = 'root@master:'
        self.client.run_shell_command(
            'mkfs.vfat /dev/disk/by-label/testboot -n testboot',
            response = master_str)
        self.client.run_shell_command(
            'udevadm trigger',
            response = master_str)
        self.client.run_shell_command(
            'mkdir -p /mnt/boot',
            response = master_str)
        self.client.run_shell_command(
            'mount /dev/disk/by-label/testboot /mnt/boot',
            response = master_str)
        self.client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/boot -xzf -' % bootfs,
            response = master_str)
        self.client.run_shell_command(
            'umount /mnt/boot',
            response = master_str)

class TimeoutError(Exception):
    pass
