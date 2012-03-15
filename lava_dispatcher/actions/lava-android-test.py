#!/usr/bin/python

# Copyright (C) 2011-2012 Linaro Limited
#
# Author: Linaro Validation Team <linaro-dev@lists.linaro.org>
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
# along with this program; if not, see <http://www.gnu.org/licenses>.

import os
import logging
from datetime import datetime
from lava_dispatcher.actions import BaseAction
from lava_dispatcher.client.base import OperationFailed


class AndroidTestAction(BaseAction):

    def check_lava_android_test_installed(self):
        rc = os.system('which lava-android-test')
        if rc != 0:
            raise OperationFailed('lava-android-test has not been installed')


class cmd_lava_android_test_run(AndroidTestAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'test_name': {'type': 'string'},
            'option': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
            },
        'additionalProperties': False,
        }

    def test_name(self, test_name, timeout=-1):
        return super(cmd_lava_android_test_run, self).test_name() + \
               ' (%s)' % test_name

    def run(self, test_name, option=None, timeout=-1):
        #Make sure in test image now
        self.check_lava_android_test_installed()
        with self.client.android_tester_session() as session:
            bundle_name = test_name + "-" + datetime.now().strftime("%H%M%S")
            cmd = 'lava-android-test run %s -s %s -o %s/%s.bundle' % (
                test_name, session.dev_name, self.context.host_result_dir,
                bundle_name)
            if option is not None:
                cmd += ' -O ' + option
            logging.info("Execute command on host: %s" % cmd)
            rc = os.system(cmd)
            if rc != 0:
                raise OperationFailed(
                    "Failed to run test case(%s) on device(%s) with return "
                    "value: %s" % (test_name, session.dev_name, rc))


class cmd_lava_android_test_run_custom(AndroidTestAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'commands': {'type': 'array', 'items': {'type': 'string'},
                          'optional': True},
            'command_file': {'type': 'string', 'optional': True},
            'parser': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
            },
        'additionalProperties': False,
        }

    def test_name(self, commands=[], command_file=None, parser=None,
                  timeout=-1):
        if commands:
            return '%s (commands=[%s])' % (
                super(cmd_lava_android_test_run_custom, self).test_name(),
                ','.join(commands))
        elif command_file:
            return '%s (command-file=%s)' % (
                super(cmd_lava_android_test_run_custom, self).test_name(),
               command_file)

    def run(self, commands=[], command_file=None, parser=None, timeout=-1):
        #Make sure in test image now
        self.check_lava_android_test_installed()
        if commands or command_file:
            with self.client.android_tester_session() as session:
                bundle_name = 'custom' + "-" + datetime.now().strftime(
                                                                "%H%M%S")
                if commands:
                    option = " -c '%s'" % (' -c '.join(commands))
                elif command_file:
                    option = " -f '%s'" % (command_file)

                cmd = ("lava-android-test run-custom  %s -s %s "
                       "-o %s/%s.bundle") % (option, session.dev_name,
                                    self.context.host_result_dir,
                        bundle_name)
                if parser is not None:
                    cmd += " -p '%s'" % parser
                logging.info("Execute command on host: %s" % cmd)
                rc = os.system(cmd)
                if rc != 0:
                    raise OperationFailed(
                        "Failed to run test custom case[%s] on device(%s)"
                        " with return value: %s" % (','.join(commands),
                                                    session.dev_name, rc))


class cmd_lava_android_test_install(AndroidTestAction):
    """
    lava-test deployment to test image rootfs by chroot
    """

    parameters_schema = {
        'type': 'object',
        'properties': {
            'tests': {'type': 'array', 'items': {'type': 'string'}},
            'option': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
            },
        'additionalProperties': False,
        }

    def run(self, tests, option=None, timeout=2400):
        self.check_lava_android_test_installed()
        with self.client.android_tester_session() as session:
            for test in tests:
                cmd = 'lava-android-test install %s -s %s' % (
                    test, session.dev_name)
                if option is not None:
                    cmd += ' -o ' + option
                logging.info("Execute command on host: %s" % cmd)
                rc = os.system(cmd)
                if rc != 0:
                    raise OperationFailed(
                        "Failed to install test case(%s) on device(%s) with "
                        "return value: %s" % (test, session.dev_name, rc))
