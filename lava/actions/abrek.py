#!/usr/bin/python
from lava.actions import BaseAction
from lava.client import OperationFailed
from lava.config import LAVA_RESULT_DIR, MASTER_STR, TESTER_STR

class cmd_test_abrek(BaseAction):
    def run(self, test_name, timeout=-1):
        #Make sure in test image now
        self.in_test_shell()

        self.client.run_shell_command('mkdir -p %s' % LAVA_RESULT_DIR,
            response = TESTER_STR)

        self.client.run_shell_command(
            'abrek run %s -o %s/%s.bundle' % (
                test_name, LAVA_RESULT_DIR, test_name),
            response = TESTER_STR, timeout = timeout)

class cmd_install_abrek(BaseAction):
    """
    abrek test tool deployment to test image rootfs by chroot
    """
    def run(self, tests):
        #Make sure in master image
        #, or exception can be caught and do boot_master_image()
        try:
            self.client.in_master_shell()
        except:
            self.client.boot_master_image()

        #install bazaar in tester image
        self.client.run_shell_command(
            'mkdir -p /mnt/root',
            response = MASTER_STR)
        self.client.run_shell_command(
            'mount /dev/disk/by-label/testrootfs /mnt/root',
            response = MASTER_STR)
        self.client.run_shell_command(
            'cp -f /mnt/root/etc/resolv.conf /mnt/root/etc/resolv.conf.bak',
            response = MASTER_STR)
        self.client.run_shell_command(
            'cp -L /etc/resolv.conf /mnt/root/etc',
            response = MASTER_STR)
        #eliminate warning: Can not write log, openpty() failed 
        #                   (/dev/pts not mounted?), does not work
        self.client.run_shell_command(
            'mount --rbind /dev /mnt/root/dev',
            response = MASTER_STR)
        self.client.run_shell_command(
            'chroot /mnt/root apt-get update',
            response = MASTER_STR)
        #Install necessary packages for build abrek
        self.client.run_shell_command(
            'chroot /mnt/root apt-get -y install bzr python-apt python-distutils-extra',
            response = MASTER_STR)
        self.client.run_shell_command(
            'chroot /mnt/root bzr branch lp:abrek',
            response = MASTER_STR)
        self.client.run_shell_command(
            'chroot /mnt/root sh -c "cd abrek && python setup.py install"',
            response = MASTER_STR)

        #Test if abrek installed
        try:
            self.client.run_shell_command(
                'chroot /mnt/root abrek help',
                response = "list-tests", timeout = 10)
        except:
            raise OperationFailed("abrek deployment failed")

        for test in tests:
            self.client.run_shell_command(
                'chroot /mnt/root abrek install %s' % test,
                response = MASTER_STR)
        #clean up
        self.client.run_shell_command(
            'cp -f /mnt/root/etc/resolv.conf.bak /mnt/root/etc/resolv.conf',
            response = MASTER_STR)
        self.client.run_shell_command(
            'rm -rf /mnt/root/abrek',
            response = MASTER_STR)
        self.client.run_shell_command(
            'cat /proc/mounts | awk \'{print $2}\' | grep "^/mnt/root/dev" | sort -r | xargs umount',
            response = MASTER_STR)
        self.client.run_shell_command(
            'umount /mnt/root',
            response = MASTER_STR)
