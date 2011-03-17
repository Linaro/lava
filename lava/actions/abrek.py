#!/usr/bin/python
from lava.actions import BaseAction
from lava.client import OperationFailed

class cmd_test_abrek(BaseAction):
    def run(self, test_name, timeout=-1):
        tester_str = "root@localhost:"
        print "abrek run %s" % test_name

        #Make sure in test image now
        self.in_test_shell()

        self.client.run_shell_command('mkdir -p /lava/results',
            response = tester_str)

        self.client.run_shell_command(
                'abrek run %s -o /lava/results/%s' % (test_name, test_name),
            response = tester_str, timeout = timeout)

class cmd_install_abrek(BaseAction):
    """
    abrek test tool deployment to test image rootfs by chroot
    may be placed in deploy.py, it can move later
    """
    def run(self, tests):
        #Make sure in master image
        #, or exception can be caught and do boot_master_image()
        master_str = "root@master:"
        self.client.in_master_shell()
        #install bazaar in tester image
        self.client.run_shell_command(
            'mkdir -p /mnt/root',
            response = master_str)
        self.client.run_shell_command(
            'mount /dev/disk/by-label/testrootfs /mnt/root',
            response = master_str)
        self.client.run_shell_command(
            'cp -L /etc/resolv.conf /mnt/root/etc',
            response = master_str)
        self.client.run_shell_command(
            'cp -L /etc/apt/apt.conf.d/70debconf /mnt/root/etc/apt/apt.conf.d',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root mount -t proc proc /proc',
            response = master_str)
        #elimite warning: Can not write log, openpty() failed 
        #                   (/dev/pts not mounted?), does not work
        self.client.run_shell_command(
            'chroot /mnt/root mount --rbind /dev /mnt/root/dev',
            response = master_str)
        #ensure no libc6 config dialog popout when apt-get
        self.client.run_shell_command(
            'chroot /mnt/root stop cron',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root apt-get update',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root apt-get -y install bzr',
            response = master_str)
        #Two necessary packages for build abrek
        self.client.run_shell_command(
            'chroot /mnt/root apt-get -y install python-distutils-extra',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root apt-get -y install python-apt',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root bzr branch lp:abrek',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root sh -c "cd abrek && python setup.py install"',
            response = master_str)
        #Test if abrek installed
        self.client.run_shell_command(
            'chroot /mnt/root abrek help',
            response = "list-tests")
        for test in tests:
            self.client.run_shell_command(
                'chroot /mnt/root abrek install %s' % test,
                response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root umount /proc',
            response = master_str)
