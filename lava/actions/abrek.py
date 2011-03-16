#!/usr/bin/python
from lava.actions import BaseAction
from lava.client import OperationFailed

class cmd_test_abrek(BaseAction):
    def run(self, test_name, timeout=-1):
        print "abrek run %s" % test_name

        #Make sure in test image now, abrek will install in master image
        self.in_test_shell()

        self.test_abrek(self, test_name, timeout)

    def test_abrek(self, test_name, timeout):
        """
        Invoke test suite by abrek
        """
        self.client.run_shell_command('abrek run %s' % test_name,
            response = self.tester_str, timeout)

    """
    Define tester_str temply, should be a constant imported from other module
    """
    tester_str = "root@localhost:"

class cmd_deploy_abrek(BaseAction):
    """
    abrek test tool deployment to test image rootfs by chroot
    Would like to implement a new command, may be placed in deploy.py, 
    it can move later
    """
    def run(self):
        #Make sure in master image
        #, or exception can be caught and do boot_master_image()
        self.client.in_master_shell()
        #install bazaar in tester image
        self.client.run_shell_command(
            'mkdir -p /mnt/root',
            response = master_str)
        self.client.run_shell_command(
            'mount /dev/disk/by-label/testrootfs /mnt/root',
            response = master_str)
        #does it need to change to a temp path to install abrek
        #does it need to restore old resolv.conf
        self.client.run_shell_command(
            'cp -L /etc/resolv.conf /mnt/root/etc',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root mount -t proc proc /proc',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root apt-get update',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root apt-get -y install bzr',
            response = master_str)
        #A necessary package for build abrek
        self.client.run_shell_command(
            'chroot /mnt/root apt-get -y install python-distutils-extra',
            response = master_str)
        self.client.run_shell_command(
            'chroot /mnt/root bzr branch lp:abrek',
            response = master_str)
        #abrek installation, not implemnt yet
        self.client.run_shell_command(
            'chroot /mnt/root umount /proc',
            response = master_str)

    master_str = "root@master:"
