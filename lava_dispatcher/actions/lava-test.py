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
from lava_dispatcher.client.base import OperationFailed, CriticalError


def _install_lava_test(client, session):
    #install bazaar in tester image
    session.run('apt-get update')
    #Install necessary packages for build lava-test
    cmd = ('apt-get -y install '
           'bzr usbutils python-apt python-setuptools python-simplejson lsb-release')
    session.run(cmd, timeout=2400)
    session.run("apt-get -y install python-pip")

    dispatcher_config = client.context.config
    lava_test_url = dispatcher_config.get("LAVA_TEST_URL")
    logging.debug("Installing %s with pip" % lava_test_url)
    session.run('pip install -e ' + lava_test_url)

    #Test if lava-test installed
    try:
        rc = session.run('lava-test -h', response="list-test", timeout=60)
    except:
        tb = traceback.format_exc()
        client.sio.write(tb)
        logging.error("lava-test deployment failed")
        raise CriticalError("lava-test deployment failed")
    if rc != 0:
        logging.error("lava-test deployment failed")
        raise CriticalError("lava-test deployment failed")

class cmd_lava_test_run(BaseAction):

    def test_name(self, test_name, test_options = "", timeout=-1):
        return super(cmd_lava_test_run, self).test_name() + ' (%s)' % test_name

    def run(self, test_name, test_options = "", timeout=-1):
        logging.info("Executing lava_test_run %s command" % test_name)
        with self.client.tester_session() as session:
            session.run('mkdir -p %s' % self.context.lava_result_dir)
            session.export_display()
            bundle_name = test_name + "-" + datetime.now().strftime("%H%M%S")

            if test_options != "":
                test_options = "-t '%s'" % test_options

            cmd = ('lava-test run %s %s -o %s/%s.bundle' % (
                    test_name, test_options, self.context.lava_result_dir, bundle_name))
            try:
                rc = session.run(cmd, timeout=timeout)
            except:
                logging.exception("session.run failed")
                self.client.proc.sendcontrol('c')
                try:
                    session.run('true', timeout=20)
                except:
                    logging.exception("killing test failed, rebooting")
                    self.client.boot_linaro_image()
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

        with self.client.reliable_session() as session:

            _install_lava_test(self.client, session)

            if install_python:
                for module in install_python:
                    session.run("pip install -e " + module)

            if register:
                for test_def_url in register:
                    session.run('lava-test register-test  ' + test_def_url,
                        timeout=60)

            for test in tests:
                session.run('lava-test install %s' % test, timeout=timeout)

            session.run('rm -rf lava-test', timeout=60)


class cmd_add_apt_repository(BaseAction):
    """
    add apt repository to test image rootfs by chroot
    arg could be 'deb uri distribution [component1] [component2][...]' or ppa:<ppa_name>
    """
    def run(self, arg):
        with self.client.reliable_session() as session:

            #install add-apt-repository
            session.run('apt-get -y install python-software-properties')

            #add ppa
            session.run('add-apt-repository %s < /dev/null' % arg[0])
            session.run('apt-get update')
