#!/usr/bin/python
from lava.dispatcher.actions import BaseAction
from lava.dispatcher.config import LAVA_IMAGE_TMPDIR, LAVA_IMAGE_URL, MASTER_STR
import os
import shutil
from tempfile import mkdtemp
from lava.dispatcher.utils import download, download_with_cache

class cmd_deploy_linaro_android_image(BaseAction):
    def run(self, boot, system, data, use_cache=True):
        client = self.client
        print "deploying Android on %s" % client.hostname
        print "  boot: %s" % boot
        print "  system: %s" % system
        print "  data: %s" % data
        print "Booting master image"
        client.boot_master_image()

        print "Waiting for network to come up"
        client.wait_network_up()

        boot_tbz2, system_tbz2, data_tbz2 = self.download_tarballs(boot,
            system, data, use_cache)

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
            shutil.rmtree(self.tarball_dir)
            raise CriticalError("Android deployment failed")

    def download_tarballs(self, boot_url, system_url, data_url, use_cache=True):
        """Download tarballs from a boot, system and data tarball url

        :param boot_url: url of the Linaro Android boot tarball to download
        :param system_url: url of the Linaro Android system tarball to download
        :param data_url: url of the Linaro Android data tarball to download
        :param use_cache: whether or not to use the cached copy (if it exists)
        """
        self.tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        tarball_dir = self.tarball_dir
        os.chmod(tarball_dir, 0755)

        if use_cache:
            boot_path = download_with_cache(boot_url, tarball_dir)
            system_path = download_with_cache(system_url, tarball_dir)
            data_path = download_with_cache(data_url, tarball_dir)
        else:
            boot_path = download(boot_url, tarball_dir)
            system_path = download(system_url, tarball_dir)
            data_path = download(data_url, tarball_dir)
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

        self.recreate_uInitrd()

        client.run_shell_command(
            'umount /mnt/lava/boot',
            response = MASTER_STR)

    def recreate_uInitrd(self):
        client = self.client
        client.run_shell_command(
            'mkdir -p ~/tmp/',
            response = MASTER_STR)
        client.run_shell_command(
            'mv /mnt/lava/boot/uInitrd ~/tmp',
            response = MASTER_STR)
        client.run_shell_command(
            'cd ~/tmp/',
            response = MASTER_STR)

        client.run_shell_command(
            'dd if=uInitrd of=uInitrd.data ibs=64 skip=1',
            response = MASTER_STR)
        client.run_shell_command(
            'mv uInitrd.data ramdisk.cpio.gz',
            response = MASTER_STR)
        client.run_shell_command(
            'gzip -d ramdisk.cpio.gz; cpio -i -F ramdisk.cpio',
            response = MASTER_STR)
        client.run_shell_command(
            'sed -i "/mount ext4 \/dev\/block\/mmcblk0p3/d" init.rc',
            response = MASTER_STR)
        client.run_shell_command(
            'sed -i "/mount ext4 \/dev\/block\/mmcblk0p5/d" init.rc',
            response = MASTER_STR)
        client.run_shell_command(
            'sed -i "s/mmcblk0p2/mmcblk0p5/g" init.rc',
            response = MASTER_STR)
        client.run_shell_command(
            'sed -i "/export PATH/a \ \ \ \ export PS1 android# " init.rc',
            response = MASTER_STR)

        client.run_shell_command(
            'cpio -i -t -F ramdisk.cpio | cpio -o -H newc | \
                gzip > ramdisk_new.cpio.gz',
            response = MASTER_STR)

        client.run_shell_command(
            'mkimage -A arm -O linux -T ramdisk -n "Android Ramdisk Image" \
                -d ramdisk_new.cpio.gz uInitrd',
            response = MASTER_STR)

        client.run_shell_command(
            'cd -',
            response = MASTER_STR)
        client.run_shell_command(
            'mv ~/tmp/uInitrd /mnt/lava/boot/uInitrd',
            response = MASTER_STR)
        client.run_shell_command(
            'rm -rf ~/tmp',
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

        sed_cmd = "/dev_mount sdcard \/mnt\/sdcard/c dev_mount sdcard /mnt/sdcard 6 " \
            "/devices/platform/omap/omap_hsmmc.0/mmc_host/mmc0"
        client.run_shell_command(
            'sed -i "%s" /mnt/lava/system/etc/vold.fstab' % sed_cmd,
            response = MASTER_STR)
        client.run_shell_command(
            'umount /mnt/lava/system',
            response = MASTER_STR)

    def purge_linaro_android_sdcard(self):
        client = self.client
        client.run_shell_command(
            'mkfs.vfat /dev/disk/by-label/sdcard -n sdcard',
            response = MASTER_STR)
        client.run_shell_command(
            'udevadm trigger',
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
