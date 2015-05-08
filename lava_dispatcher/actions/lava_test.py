#!/usr/bin/python

# Copyright (C) 2011-2012 Linaro Limited
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

import logging

from lava_dispatcher.actions import BaseAction
from lava_dispatcher.errors import OperationFailed
from lava_dispatcher.utils import generate_bundle_file_name


def _install_lava_test(client, session):
    # install bazaar in tester image
    session.run('%s update' % client.aptget_cmd)
    # Install necessary packages for build lava-test
    cmd = ('%s -y --force-yes install '
           'bzr usbutils python-apt python-setuptools '
           'python-simplejson lsb-release python-keyring '
           'python-pip' % client.aptget_cmd)
    session.run(cmd, timeout=2400)

    dispatcher_config = client.context.config

    lava_test_deb = dispatcher_config.lava_test_deb
    if lava_test_deb:
        logging.debug("Installing %s with apt-get" % lava_test_deb)
        session.run("%s -y --force-yes install %s" %
                    (client.aptget_cmd, lava_test_deb))
    else:
        lava_test_url = dispatcher_config.lava_test_url
        logging.debug("Installing %s with pip" % lava_test_url)
        session.run('pip install -e ' + lava_test_url)

    # Test if lava-test installed
    session.run('which lava-test', timeout=60)

    # cleanup the lava-test - old results, cached files...
    session.run('lava-test reset', timeout=60)


class cmd_lava_test_run(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'test_name': {'type': 'string'},
            'test_options': {'type': 'string', 'optional': True},
            'role': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
        },
        'additionalProperties': False,
    }

    def test_name(self, test_name, test_options="", timeout=-1):
        return super(cmd_lava_test_run, self).test_name() + ' (%s)' % test_name

    def run(self, test_name, test_options="", timeout=-1):
        self.context.any_device_bundles = True
        logging.info("Executing lava_test_run %s command" % test_name)
        with self.client.tester_session() as session:
            session.run('mkdir -p %s' % self.context.config.lava_result_dir)
            session.export_display()
            bundle_name = generate_bundle_file_name(test_name)
            if test_options != "":
                test_options = "-t '%s'" % test_options

            cmd = ('lava-test run %s %s -o %s/%s.bundle' %
                   (test_name, test_options,
                    self.context.config.lava_result_dir, bundle_name))
            try:
                rc = session.run(cmd, timeout=timeout)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except:
                logging.exception("session.run failed")
                self.client.proc.sendcontrol('c')
                try:
                    session.run('true', timeout=20)
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except:
                    logging.exception("killing test failed, rebooting")
                    self.client.boot_linaro_image()
                raise
            finally:
                # try to make sure the test bundle is safely written to disk
                session.run('sync', timeout=60)

            if rc is None:
                raise OperationFailed("test case getting return value failed")
            elif rc != 0:
                raise OperationFailed(
                    "test case failed with return value: %s" % rc)


class cmd_lava_test_install(BaseAction):
    """
    lava-test deployment to test image rootfs by chroot
    """

    parameters_schema = {
        'type': 'object',
        'properties': {
            'tests': {'type': 'array', 'items': {'type': 'string'}},
            'install_python': {
                'type': 'array', 'items': {'type': 'string'}, 'optional': True
            },
            'install_deb': {
                'type': 'array', 'items': {'type': 'string'}, 'optional': True
            },
            'register': {
                'type': 'array', 'items': {'type': 'string'}, 'optional': True
            },
            'timeout': {'type': 'integer', 'optional': True},
            'role': {'type': 'string', 'optional': True},
            'install_lava_test': {'type': 'boolean', 'optional': True, 'default': True}
        },
        'additionalProperties': False,
    }

    def run_command_with_test_result(self, session, command, test_result_name, timeout):
        try:
            session.run(command, timeout=timeout)
        except OperationFailed as e:
            logging.error("running %r failed" % command)
            self.context.test_data.add_result(test_result_name, 'fail', str(e))
        else:
            self.context.test_data.add_result(test_result_name, 'pass')

    def run(self, tests, install_python=None, install_deb=None, register=None,
            timeout=2400, install_lava_test=True):
        logging.info(
            "Executing lava_test_install (%s) command" % ",".join(tests))

        with self.client.reliable_session() as session:

            lava_proxy = self.context.config.lava_proxy
            if lava_proxy:
                session.run("sh -c 'export http_proxy=%s'" % lava_proxy)

            lava_no_proxy = self.context.config.lava_no_proxy
            if lava_no_proxy:
                session.run("sh -c 'export no_proxy=%s'" % lava_no_proxy)

            if install_lava_test:
                _install_lava_test(self.client, session)

            if install_python:
                for module in install_python:
                    self.run_command_with_test_result(
                        session, "pip install -e " + module,
                        'lava_test_install python (%s)' % module, timeout=60)

            if install_deb:
                debs = " ".join(install_deb)
                self.run_command_with_test_result(
                    session, "%s -y --force-yes install %s"
                    % (self.client.aptget_cmd, debs),
                    'lava_test_install deb (%s)' % debs, timeout=timeout)

            if register:
                for test_def_url in register:
                    self.run_command_with_test_result(
                        session, 'lava-test register-test  ' + test_def_url,
                        'lava_test_install register (%s)' % test_def_url, timeout=60)

            for test in tests:
                self.run_command_with_test_result(
                    session, 'lava-test install %s' % test,
                    'lava_test_install (%s)' % test, timeout=timeout)

            session.run('rm -rf lava-test', timeout=60)


class cmd_add_apt_repository(BaseAction):
    """
    add apt repository to test image rootfs by chroot
    arg could be 'deb uri distribution [component1] [component2][...]'
    or ppa:<ppa_name>
    """

    parameters_schema = {
        'type': 'object',
        'properties': {
            'arg': {
                'type': 'array',
                'items': {'type': 'string'},
            }
        },
        'additionalProperties': False,
    }

    def run(self, arg):
        with self.client.reliable_session() as session:

            # install add-apt-repository
            session.run('%s -y install python-software-properties' %
                        self.client.aptget_cmd)

            # add ppa
            for repository in arg:
                session.run('add-apt-repository %s < /dev/null' % repository)
            session.run('%s update' % self.client.aptget_cmd)
