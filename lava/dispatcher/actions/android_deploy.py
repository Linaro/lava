#!/usr/bin/python
from commands import getoutput, getstatusoutput
from lava.dispatcher.actions import BaseAction
from lava.dispatcher.config import LAVA_IMAGE_TMPDIR, LAVA_IMAGE_URL, MASTER_STR
import os
import re
import shutil
from tempfile import mkdtemp
import urllib2
import urlparse

class cmd_deploy_linaro_android_image(cmd_deploy_linaro_image):
    def run(self, boot, system, data):
        client = self.client
        print "deploying Android on %s" % client.hostname
        print "  boot: %s" % boot
        print "  system: %s" % system
        print "  data: %s" % data
        print "Booting master image"
        client.boot_master_image()

        print "Waiting for network to come up"
        client.wait_network_up()

        boot_tbz2, system_tbz2, data_tbz2 = self.download_tarballs(boot, system, data)

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
        except:
            shutil.rmtree(self.tarball_dir)
            raise

    def download_tarballs(self, boot_url, system_url, data_url):
        """Download tarballs from a boot, system and data tarball url

        :param boot_url: url of the Linaro Android boot tarball to download
        :param system_url: url of the Linaro Android system tarball to download
        :param data_url: url of the Linaro Android data tarball to download
        """
        self.tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        tarball_dir = self.tarball_dir
        os.chmod(tarball_dir, 0755)

        boot_path = self._download(boot_url, tarball_dir)
        system_path = self._download(system_url, tarball_dir)
        data_path = self._download(data_url, tarball_dir)
        return  boot_path, system_path, data_path

    def deploy_linaro_android_testboot(self, boottbz2):
        client = self.client
        client.run_shell_command(
            'mkfs.vfat /dev/disk/by-label/testboot -n testboot',
            response = MASTER_STR)
        client.run_shell_command(
            'udevadm trigger',
            response = MASTER_STR)
        client.run_shell_command(
            'mkdir -p /mnt/lava/boot',
            response = MASTER_STR)
        client.run_shell_command(
            'mount /dev/disk/by-label/testboot /mnt/lava/boot',
            response = MASTER_STR)
        client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/lava -xjf -' % boottbz2,
            response = MASTER_STR)
        client.run_shell_command(
            'umount /mnt/lava/boot',
            response = MASTER_STR)

    def deploy_linaro_android_testrootfs(self, systemtbz2):
        client = self.client
        client.run_shell_command(
            'mkfs.ext4 -q /dev/disk/by-label/testrootfs -L testrootfs',
            response = MASTER_STR)
        client.run_shell_command(
            'udevadm trigger',
            response = MASTER_STR)
        client.run_shell_command(
            'mkdir -p /mnt/lava/system',
            response = MASTER_STR)
        client.run_shell_command(
            'mount /dev/disk/by-label/testrootfs /mnt/lava/system',
            response = MASTER_STR)
        client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/lava -xjf -' % systemtbz2,
            response = MASTER_STR, timeout = 600)
        client.run_shell_command(
            'umount /mnt/lava/system',
            response = MASTER_STR)

    def deploy_linaro_android_system(self, systemtbz2):
        client = self.client
        client.run_shell_command(
            'mkfs.ext4 -q /dev/disk/by-label/system -L system',
            response = MASTER_STR)
        client.run_shell_command(
            'udevadm trigger',
            response = MASTER_STR)
        client.run_shell_command(
            'mkdir -p /mnt/lava/system',
            response = MASTER_STR)
        client.run_shell_command(
            'mount /dev/disk/by-label/system /mnt/lava/system',
            response = MASTER_STR)
        client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/lava -xjf -' % systemtbz2,
            response = MASTER_STR, timeout = 600)
        client.run_shell_command(
            'umount /mnt/lava/system',
            response = MASTER_STR)

    def deploy_linaro_android_data(self, datatbz2):
        client = self.client
        client.run_shell_command(
            'mkfs.ext4 -q /dev/disk/by-label/data -L data',
            response = MASTER_STR)
        client.run_shell_command(
            'udevadm trigger',
            response = MASTER_STR)
        client.run_shell_command(
            'mkdir -p /mnt/lava/data',
            response = MASTER_STR)
        client.run_shell_command(
            'mount /dev/disk/by-label/data /mnt/lava/data',
            response = MASTER_STR)
        client.run_shell_command(
            'wget -qO- %s |tar --numeric-owner -C /mnt/lava -xjf -' % datatbz2,
            response = MASTER_STR, timeout = 600)
        client.run_shell_command(
            'umount /mnt/lava/data',
            response = MASTER_STR)
