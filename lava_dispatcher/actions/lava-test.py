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
import logging
import traceback

from lava_dispatcher.actions import BaseAction
from lava_dispatcher.client import OperationFailed, CriticalError
from lava_dispatcher.config import get_config

def _setup_testrootfs(client):
    #Make sure in master image
    #, or exception can be caught and do boot_master_image()
    try:
        client.in_master_shell()
    except:
        logging.exception("in_master_shell failed")
        client.boot_master_image()

    client.run_cmd_master('mkdir -p /mnt/root')
    client.run_cmd_master('mount /dev/disk/by-label/testrootfs /mnt/root')
    client.run_cmd_master(
        'cp -f /mnt/root/etc/resolv.conf /mnt/root/etc/resolv.conf.bak')
    client.run_cmd_master('cp -L /etc/resolv.conf /mnt/root/etc')
    #eliminate warning: Can not write log, openpty() failed
    #                   (/dev/pts not mounted?), does not work
    client.run_cmd_master('mount --rbind /dev /mnt/root/dev')


def _teardown_testrootfs(client):
    client.run_cmd_master(
        'cp -f /mnt/root/etc/resolv.conf.bak /mnt/root/etc/resolv.conf')
    cmd = ('cat /proc/mounts | awk \'{print $2}\' | grep "^/mnt/root/dev"'
        '| sort -r | xargs umount')
    client.run_cmd_master(cmd)
    client.run_cmd_master('umount /mnt/root')


def _install_lava_test(client):
    #install bazaar in tester image
    client.run_cmd_master(
        'chroot /mnt/root apt-get update')
    #Install necessary packages for build lava-test
    cmd = ('chroot /mnt/root apt-get -y install bzr usbutils python-apt '
        'python-setuptools python-simplejson lsb-release')
    client.run_cmd_master(cmd, timeout=2400)
    client.run_cmd_master("chroot /mnt/root apt-get -y install python-pip")

    dispatcher_config = get_config("lava-dispatcher")
    lava_test_url = dispatcher_config.get("LAVA_TEST_URL")
    logging.debug("Installing %s with pip" % lava_test_url)
    client.run_cmd_master('chroot /mnt/root pip install -e ' + lava_test_url)

    #Test if lava-test installed
    try:
        client.run_shell_command(
            'chroot /mnt/root lava-test help',
            response="list-test", timeout=60)
    except:
        tb = traceback.format_exc()
        client.sio.write(tb)
        raise CriticalError("lava-test deployment failed")


class cmd_lava_test_run(BaseAction):

    def test_name(self, test_name, test_options = "", timeout=-1):
        return super(cmd_lava_test_run, self).test_name() + ' (%s)' % test_name

    def run(self, test_name, test_options = "", timeout=-1):
        logging.info("Executing lava_test_run %s command" % test_name)
        #Make sure in test image now
        client = self.client
        try:
            client.in_test_shell()
        except:
            client.boot_linaro_image()
        client.run_cmd_tester('mkdir -p %s' % self.context.lava_result_dir)
        client.export_display()
        bundle_name = test_name + "-" + datetime.now().strftime("%H%M%S")

        if test_options != "":
            test_options = "-t '%s'" % test_options

        cmd = ('lava-test run %s %s -o %s/%s.bundle' % (
                test_name, test_options, self.context.lava_result_dir, bundle_name))
        try:
            rc = client.run_cmd_tester(cmd, timeout=timeout)
        except:
            logging.exception("run_cmd_tester failed")
            client.proc.sendcontrol('c')
            try:
                client.run_cmd_tester('true', timeout=20)
            except:
                logging.exception("run_cmd_tester true failed, rebooting")
                client.boot_linaro_image()
            raise
        if rc is None:
            raise OperationFailed("test case getting return value failed")
        elif rc != 0:
            raise OperationFailed("test case failed with return value: %s" % rc)

class cmd_lava_test_install(BaseAction):
    """
    lava-test deployment to test image rootfs by chroot
    """
    def run(self, tests, install_python = None, register = None, timeout=2400):
        logging.info("Executing lava_test_install (%s) command" % ",".join(tests))
        client = self.client

        _setup_testrootfs(client)
        _install_lava_test(client)

        if install_python:
            for module in install_python:
                client.run_cmd_master("chroot /mnt/root pip install -e " + module)

        if register:
            for test_def_url in register:
                client.run_cmd_master('chroot /mnt/root lava-test register-test  ' + test_def_url)

        for test in tests:
            client.run_cmd_master(
                'chroot /mnt/root lava-test install %s' % test)

        client.run_cmd_master('rm -rf /mnt/root/lava-test')

        _teardown_testrootfs(client)


class cmd_add_apt_repository(BaseAction):
    """
    add apt repository to test image rootfs by chroot
    arg could be 'deb uri distribution [component1] [component2][...]' or ppm:<ppa_name>
    """
    def run(self, arg):
        client = self.client
        _setup_testrootfs(client)

        #install add-apt-repository
        client.run_cmd_master('chroot /mnt/root apt-get -y install python-software-properties')

        #add ppa
        client.run_cmd_master('chroot /mnt/root add-apt-repository %s < /dev/null' % arg[0])
        client.run_cmd_master('chroot /mnt/root apt-get update')

        _teardown_testrootfs(client)
