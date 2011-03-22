#!/usr/bin/python
from lava.actions import BaseAction
from lava.client import OperationFailed

class cmd_test_abrek(BaseAction):
    def run(self, test_name, timeout=-1):
        tester_str = "root@localhost:"
        #Make sure in test image now
        self.in_test_shell()

        self.client.run_shell_command('mkdir -p /lava/results',
            response = tester_str)

        self.client.run_shell_command(
            'abrek run %s -o /lava/results/%s.bundle' % (test_name, test_name),
            response = tester_str, timeout = timeout)

class cmd_install_abrek(BaseAction):
    """
    abrek test tool deployment to test image rootfs by chroot
    """
    def run(self, tests):
        #Make sure in master image
        #, or exception can be caught and do boot_master_image()
        master_str = "root@master:"
        try:
            self.client.in_master_shell()
        except:
            self.client.boot_master_image()

        #install bazaar in tester image
        self.client.run_shell_command(
            'mkdir -p /mnt/root',
            response = master_str)
        self.client.run_shell_command(
            'mount /dev/disk/by-label/testrootfs /mnt/root',
            response = master_str)
        self.client.run_shell_command(
            'cp -f /mnt/root/etc/resolv.conf /mnt/root/etc/resolv.conf.bak',
            response = master_str)
        self.client.run_shell_command(
            'cp -L /etc/resolv.conf /mnt/root/etc',
            response = master_str)
        #eliminate warning: Can not write log, openpty() failed 
        #                   (/dev/pts not mounted?), does not work
        self.client.run_shell_command(
            'mount --rbind /dev /mnt/root/dev',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root apt-get update',
            response = master_str)
        #Install necessary packages for build abrek
        self.client.run_shell_command(
            'chroot /mnt/root apt-get -y install bzr python-apt python-distutils-extra',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root bzr branch lp:abrek',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root sh -c "cd abrek && python setup.py install"',
            response = master_str)

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
                response = master_str)
        #clean up
        self.client.run_shell_command(
            'cp -f /mnt/root/etc/resolv.conf.bak /mnt/root/etc/resolv.conf',
            response = master_str)
        self.client.run_shell_command(
            'rm -rf /mnt/root/abrek',
            response = master_str)
        self.client.run_shell_command(
            'cat /proc/mounts | awk \'{print $2}\' | grep "^/mnt/root/dev" | sort -r | xargs umount',
            response = master_str)
        self.client.run_shell_command(
            'umount /mnt/root',
            response = master_str)
