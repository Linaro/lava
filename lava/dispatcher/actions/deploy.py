#!/usr/bin/python
from commands import getoutput, getstatusoutput
import os
import re
import shutil
from tempfile import mkdtemp
import urllib2
import urlparse

from lava.dispatcher.actions import BaseAction
from lava.dispatcher.config import (LAVA_IMAGE_TMPDIR,
                                    LAVA_IMAGE_URL,
                                    MASTER_STR,
                                    LAVA_CACHEDIR)


class cmd_deploy_linaro_image(BaseAction):
    def run(self, hwpack, rootfs, use_cache=True):
        client = self.client
        print "deploying on %s" % client.hostname
        print "  hwpack: %s" % hwpack
        print "  rootfs: %s" % rootfs
        print "Booting master image"
        client.boot_master_image()

        print "Waiting for network to come up"
        client.wait_network_up()
        boot_tgz, root_tgz = self.generate_tarballs(hwpack, rootfs, use_cache)
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
            shutil.rmtree(self.tarball_dir)
            raise

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

    def _url_to_cache(self, url):
        url_parts = urlparse.urlsplit(url)
        path = os.path.join(LAVA_CACHEDIR, url_parts.netloc,
            url_parts.path.lstrip(os.sep))
        return path

    def generate_tarballs(self, hwpack_url, rootfs_url, use_cache):
        """Generate tarballs from a hwpack and rootfs url

        :param hwpack_url: url of the Linaro hwpack to download
        :param rootfs_url: url of the Linaro image to download
        """
        client = self.client
        self.tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        tarball_dir = self.tarball_dir
        os.chmod(tarball_dir, 0755)
        if use_cache:
            hwpack_cache_loc = self._url_to_cache(hwpack_url)
            rootfs_cache_loc = self._url_to_cache(rootfs_url)
            if os.path.exists(hwpack_cache_loc):
                hwpack_filename = os.path.basename(hwpack_cache_loc)
                hwpack_path = os.path.join(tarball_dir, hwpack_filename)
                os.link(hwpack_cache_loc, hwpack_path)
            else:
                hwpack_path = self._download(hwpack_url, tarball_dir)
                try:
                    os.makedirs(os.path.dirname(hwpack_cache_loc))
                    os.link(hwpack_path, hwpack_cache_loc)
                except:
                    #If this fails, it will be because another test is
                    #pulling the same image at the same time, so ignore
                    pass

            if os.path.exists(rootfs_cache_loc):
                rootfs_filename = os.path.basename(rootfs_cache_loc)
                rootfs_path = os.path.join(tarball_dir, rootfs_filename)
                os.link(rootfs_cache_loc, rootfs_path)
            else:
                rootfs_path = self._download(rootfs_url, tarball_dir)
                try:
                    os.makedirs(os.path.dirname(rootfs_cache_loc))
                    os.link(rootfs_path, rootfs_cache_loc)
                except:
                    #If this fails, it will be because another test is
                    #pulling the same image at the same time, so ignore
                    pass
        else:
            hwpack_path = self._download(hwpack_url, tarball_dir)
            rootfs_path = self._download(rootfs_url, tarball_dir)

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

