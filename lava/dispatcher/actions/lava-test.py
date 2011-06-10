#!/usr/bin/python
from lava.dispatcher.actions import BaseAction
from lava.dispatcher.client import OperationFailed
from lava.dispatcher.config import LAVA_RESULT_DIR, MASTER_STR, TESTER_STR

class cmd_lava_test_run(BaseAction):
    def run(self, test_name, timeout=-1):
        #Make sure in test image now
        client = self.client
        client.in_test_shell()
        client.run_shell_command('mkdir -p %s' % LAVA_RESULT_DIR,
            response = TESTER_STR)
        client.export_display()
        client.run_shell_command(
            'lava-test run %s -o %s/%s.bundle' % (
                test_name, LAVA_RESULT_DIR, test_name),
            response = TESTER_STR, timeout = timeout)

class cmd_lava_test_install(BaseAction):
    """
    lava-test deployment to test image rootfs by chroot
    """
    def run(self, tests, timeout=2400):
        client = self.client
        #Make sure in master image
        #, or exception can be caught and do boot_master_image()
        try:
            client.in_master_shell()
        except:
            client.boot_master_image()

        #install bazaar in tester image
        client.run_shell_command(
            'mkdir -p /mnt/root',
            response = MASTER_STR)
        client.run_shell_command(
            'mount /dev/disk/by-label/testrootfs /mnt/root',
            response = MASTER_STR)
        client.run_shell_command(
            'cp -f /mnt/root/etc/resolv.conf /mnt/root/etc/resolv.conf.bak',
            response = MASTER_STR)
        client.run_shell_command(
            'cp -L /etc/resolv.conf /mnt/root/etc',
            response = MASTER_STR)
        #eliminate warning: Can not write log, openpty() failed
        #                   (/dev/pts not mounted?), does not work
        client.run_shell_command(
            'mount --rbind /dev /mnt/root/dev',
            response = MASTER_STR)
        client.run_shell_command(
            'chroot /mnt/root apt-get update',
            response = MASTER_STR)
        #Install necessary packages for build lava-test
        client.run_shell_command(
            'chroot /mnt/root apt-get -y install bzr usbutils python-apt python-distutils-extra',
            response = MASTER_STR, timeout=2400)
        client.run_shell_command(
            'chroot /mnt/root bzr branch lp:lava-test',
            response = MASTER_STR)
        client.run_shell_command(
            'chroot /mnt/root sh -c "cd lava-test && python setup.py install"',
            response = MASTER_STR)

        #Test if lava-test installed
        try:
            client.run_shell_command(
                'chroot /mnt/root lava-test help',
                response = "list-tests")
        except:
            raise OperationFailed("lava-test deployment failed")

        for test in tests:
            client.run_shell_command(
                'chroot /mnt/root lava-test install %s' % test,
                response = MASTER_STR)
        #clean up
        client.run_shell_command(
            'cp -f /mnt/root/etc/resolv.conf.bak /mnt/root/etc/resolv.conf',
            response = MASTER_STR)
        client.run_shell_command(
            'rm -rf /mnt/root/lava-test',
            response = MASTER_STR)
        client.run_shell_command(
            'cat /proc/mounts | awk \'{print $2}\' | grep "^/mnt/root/dev" | sort -r | xargs umount',
            response = MASTER_STR)
        client.run_shell_command(
            'umount /mnt/root',
            response = MASTER_STR)
