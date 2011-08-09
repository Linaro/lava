#!/usr/bin/python

# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from datetime import datetime
from lava_dispatcher.actions import BaseAction
from lava_dispatcher.client import OperationFailed
from lava_dispatcher.config import LAVA_RESULT_DIR


class cmd_lava_test_run(BaseAction):
    def run(self, test_name, timeout=-1):
        #Make sure in test image now
        client = self.client
        client.in_test_shell()
        client.run_cmd_tester('mkdir -p %s' % LAVA_RESULT_DIR)
        client.export_display()
        bundle_name = test_name + "-" + datetime.now().strftime("%H%M%S")
        client.run_shell_command(
            'lava-test run %s -o %s/%s.bundle' % (
                test_name, LAVA_RESULT_DIR, bundle_name),
            client.tester_str, timeout)


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
        client.run_cmd_master('mkdir -p /mnt/root')
        client.run_cmd_master('mount /dev/disk/by-label/testrootfs /mnt/root')
        client.run_cmd_master('cp -f /mnt/root/etc/resolv.conf '
            '/mnt/root/etc/resolv.conf.bak')
        client.run_cmd_master('cp -L /etc/resolv.conf /mnt/root/etc')
        #eliminate warning: Can not write log, openpty() failed
        #                   (/dev/pts not mounted?), does not work
        client.run_cmd_master('mount --rbind /dev /mnt/root/dev')
        client.run_cmd_master('chroot /mnt/root apt-get update')
        #Install necessary packages for build lava-test
        cmd = ('chroot /mnt/root apt-get -y install bzr usbutils python-apt '
            'python-setuptools python-simplejson lsb-release')
        client.run_shell_command(
            cmd,
            self.client.master_str, 2400)
        client.run_cmd_master('chroot /mnt/root bzr branch lp:lava-test')
        client.run_cmd_master('chroot /mnt/root sh -c '
            '"cd lava-test && python setup.py install"')

        #Test if lava-test installed
        try:
            client.run_shell_command(
                'chroot /mnt/root lava-test help',
                "list-tests", 10)
        except:
            raise OperationFailed("lava-test deployment failed")

        for test in tests:
            client.run_cmd_master('chroot /mnt/root lava-test install %s' % test)
        #clean up
        client.run_cmd_master('cp -f /mnt/root/etc/resolv.conf.bak ' 
                '/mnt/root/etc/resolv.conf')
        client.run_cmd_master('rm -rf /mnt/root/lava-test')
        cmd = ('cat /proc/mounts | awk \'{print $2}\' | grep "^/mnt/root/dev"'
            '| sort -r | xargs umount')
        client.run_cmd_master(cmd)
        client.run_cmd_master('umount /mnt/root')
