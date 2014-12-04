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
from lava_dispatcher.actions import BaseAction
from lava_dispatcher.errors import OperationFailed, TimeoutError
from lava_dispatcher.utils import generate_bundle_file_name, DrainConsoleOutput


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
            'role': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
            'repeat': {'type': 'integer', 'optional': True},
            'repeat_count': {'type': 'integer', 'optional': True},
        },
        'additionalProperties': False,
    }

    def test_name(self, test_name, option=None, timeout=-1):
        return super(cmd_lava_android_test_run, self).test_name() + ' (%s)' % test_name

    def run(self, test_name, option=None, timeout=-1, repeat_count=0):
        # Make sure in test image now
        self.check_lava_android_test_installed()
        with self.client.android_tester_session() as session:
            bundle_name = generate_bundle_file_name(test_name)
            cmds = ["lava-android-test", 'run', test_name,
                    '-s', session.dev_name,
                    '-o', '%s/%s.bundle' % (self.context.host_result_dir,
                                            bundle_name)]
            if option is not None:
                cmds.extend(['-O', option])
            if timeout != -1:
                cmds.insert(0, 'timeout')
                cmds.insert(1, '%ss' % timeout)

            t = DrainConsoleOutput(proc=session._connection, timeout=timeout)
            t.start()
            logging.info("Execute command on host: %s" % (' '.join(cmds)))
            rc = self.context.run_command(cmds)
            t.join()
            if rc == 124:
                raise TimeoutError(
                    "The test case(%s) on device(%s) timed out" %
                    (test_name, session.dev_name))
            elif rc != 0:
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
            'role': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
            'repeat': {'type': 'integer', 'optional': True},
            'repeat_count': {'type': 'integer', 'optional': True},
        },
        'additionalProperties': False,
    }

    def test_name(self, commands=None, command_file=None, parser=None,
                  timeout=-1):
        if commands:
            return '%s (commands=[%s])' % (
                super(cmd_lava_android_test_run_custom, self).test_name(),
                ','.join(commands))
        elif command_file:
            return '%s (command-file=%s)' % (
                super(cmd_lava_android_test_run_custom, self).test_name(), command_file)

    def run(self, commands=None, command_file=None, parser=None, timeout=-1, repeat_count=0):
        """
        :param commands: a list of commands
        :param command_file: a file containing commands
        :param parser:  The parser to use for the test
        :param timeout: The timeout to apply.
        """
        # Make sure in test image now
        self.check_lava_android_test_installed()
        if commands or command_file:
            with self.client.android_tester_session() as session:
                bundle_name = generate_bundle_file_name('custom')
                cmds = ["lava-android-test", 'run-custom']
                if commands:
                    for command in commands:
                        cmds.extend(['-c', command])
                elif command_file:
                    cmds.extend(['-f', command_file])
                else:
                    raise OperationFailed(
                        "Only one of the -c and -f option can be specified"
                        " for lava_android_test_run_custom action")
                cmds.extend(['-s', session.dev_name, '-o',
                             '%s/%s.bundle' % (self.context.host_result_dir,
                                               bundle_name)])
                if parser is not None:
                    cmds.extend(['-p', parser])

                if timeout != -1:
                    cmds.insert(0, 'timeout')
                    cmds.insert(1, '%ss' % timeout)
                logging.info("Execute command on host: %s" % (' '.join(cmds)))
                rc = self.context.run_command(cmds)
                if rc == 124:
                    raise TimeoutError(
                        "The test (%s) on device(%s) timed out." %
                        (' '.join(cmds), session.dev_name))
                elif rc != 0:
                    raise OperationFailed(
                        "Failed to run test custom case[%s] on device(%s)"
                        " with return value: %s" % (' '.join(cmds),
                                                    session.dev_name, rc))


class cmd_lava_android_test_run_monkeyrunner(AndroidTestAction):
    """
    This action is added to make doing the monkeyrunner script test more easily
    from android build page. With this action, we only need to specify the url
    of the repository where the monkeyrunner script are stored.
    Then lava-android-test will run all the monkeyrunner scripts in that
    repository, and help to gather all the png files genereated when run
    """
    parameters_schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'role': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
            'repeat': {'type': 'integer', 'optional': True},
            'repeat_count': {'type': 'integer', 'optional': True},
        },
        'additionalProperties': False,
    }

    def test_name(self, url=None, timeout=-1):
        return '%s (url=[%s])' % (super(cmd_lava_android_test_run_monkeyrunner, self).test_name(), url)

    def run(self, url=None, timeout=-1, repeat_count=0):
        # Make sure in test image now
        self.check_lava_android_test_installed()
        with self.client.android_tester_session() as session:
            bundle_name = generate_bundle_file_name('monkeyrunner')
            cmds = ["lava-android-test", 'run-monkeyrunner', url]
            cmds.extend(['-s', session.dev_name, '-o',
                         '%s/%s.bundle' % (self.context.host_result_dir,
                                           bundle_name)])
            if timeout != -1:
                cmds.insert(0, 'timeout')
                cmds.insert(1, '%ss' % timeout)

            logging.info("Execute command on host: %s" % (' '.join(cmds)))
            rc = self.context.run_command(cmds)
            if rc == 124:
                raise TimeoutError("Failed to run monkeyrunner test url[%s] on device(%s)" % (url, session.dev_name))
            elif rc != 0:
                raise OperationFailed(
                    "Failed to run monkeyrunner test url[%s] on device(%s)"
                    " with return value: %s" % (url, session.dev_name, rc))


class cmd_lava_android_test_install(AndroidTestAction):
    """
    lava-test deployment to test image rootfs by chroot
    """

    parameters_schema = {
        'type': 'object',
        'properties': {
            'tests': {'type': 'array', 'items': {'type': 'string'}},
            'option': {'type': 'string', 'optional': True},
            'role': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
        },
        'additionalProperties': False,
    }

    def run(self, tests, option=None, timeout=2400):
        self.check_lava_android_test_installed()
        with self.client.android_tester_session() as session:
            for test in tests:
                cmds = ["lava-android-test", 'install',
                        test,
                        '-s', session.dev_name]
                if option is not None:
                    cmds.extend(['-o', option])
                if timeout != -1:
                    cmds.insert(0, 'timeout')
                    cmds.insert(1, '%ss' % timeout)
                logging.info("Execute command on host: %s" % (' '.join(cmds)))
                rc = self.context.run_command(cmds)
                if rc == 124:
                    raise OperationFailed(
                        "The installation of test case(%s)"
                        " on device(%s) timed out" % (test, session.dev_name))
                elif rc != 0:
                    raise OperationFailed(
                        "Failed to install test case(%s) on device(%s) with "
                        "return value: %s" % (test, session.dev_name, rc))
