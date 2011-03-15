#!/usr/bin/python
from commands import getoutput
from lava.actions import BaseAction
import os
import re
import shutil
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

    def _get_partition_offset(image, partno):
        cmd = 'parted %s -s unit b p' % image
        part_data = getoutput(cmd)
        pattern = re.compile(' %d\s+([0-9]+)' % partno)
        for line in part_data.splitlines():
            found = re.match(pattern, line)
            if found:
                return found.group(1)

    def _download(url, path=""):
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


    def generate_tarballs(self):
        """
        TODO: need to use linaro-media-create to generate an image and
        extract a tarball for bootfs and rootfs, then put them in a place
        where they can be retrived via http

        For reference, see magma-chamber branch, extract-image script
        """

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
            'wget -qO- %s |tar --numeric-owner --strip-components=1 -C /mnt/root -xzf -' % rootfs,
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
            'wget -qO- $1 |tar --numeric-owner --strip-components=1 -C /mnt/boot -xzf -' % bootfs,
            response = master_str)
        self.client.run_shell_command(
            'umount /mnt/boot',
            response = master_str)

class TimeoutError(Exception):
    pass
