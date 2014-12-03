# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort remi.duraffort@linaro.org>
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

import os
import shutil
import subprocess
import tempfile
import unittest

from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.test.test_uboot import Factory
from lava_dispatcher.pipeline.actions.boot.u_boot import UBootAction, UBootRetry
from lava_dispatcher.pipeline.power import ResetDevice, RebootDevice
from lava_dispatcher.pipeline.utils.constants import SHUTDOWN_MESSAGE
from lava_dispatcher.pipeline.action import InfrastructureError
from lava_dispatcher.pipeline.utils import vcs


class TestGit(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        self.cwd = os.getcwd()

        # Go into a temp dirctory
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

        # Create a Git repository with two commits
        subprocess.check_output(['git', 'init', 'git'])
        os.chdir('git')
        with open('test.txt', 'w') as testfile:
            testfile.write("Some data")
        subprocess.check_output(['git', 'add', 'test.txt'])
        subprocess.check_output(['git', 'commit', 'test.txt', '-m', 'First commit'],
                                env={'GIT_COMMITTER_DATE': 'Fri Oct 24 14:40:36 CEST 2014',
                                     'GIT_AUTHOR_DATE': 'Fri Oct 24 14:40:36 CEST 2014',
                                     'GIT_AUTHOR_NAME': 'Foo Bar',
                                     'GIT_AUTHOR_EMAIL': 'foo@example.com',
                                     'GIT_COMMITTER_NAME': 'Foo Bar',
                                     'GIT_COMMITTER_EMAIL': 'foo@example.com'})
        with open('second.txt', 'w') as datafile:
            datafile.write("Some more data")
        subprocess.check_output(['git', 'add', 'second.txt'])
        subprocess.check_output(['git', 'commit', 'second.txt', '-m', 'Second commit'],
                                env={'GIT_COMMITTER_DATE': 'Fri Oct 24 14:40:38 CEST 2014',
                                     'GIT_AUTHOR_DATE': 'Fri Oct 24 14:40:38 CEST 2014',
                                     'GIT_AUTHOR_NAME': 'Foo Bar',
                                     'GIT_AUTHOR_EMAIL': 'foo@example.com',
                                     'GIT_COMMITTER_NAME': 'Foo Bar',
                                     'GIT_COMMITTER_EMAIL': 'foo@example.com'})

        # Go into the tempdir
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.cwd)
        # Remove everything
        shutil.rmtree(self.tmpdir)

    def test_simple_clone(self):
        git = vcs.GitHelper('git')
        self.assertEqual(git.clone('git.clone1'), 'a7af835862da0e0592eeeac901b90e8de2cf5b67')
        self.assertEqual(git.clone('git.clone2'), 'a7af835862da0e0592eeeac901b90e8de2cf5b67')
        self.assertEqual(git.clone('git.clone3'), 'a7af835862da0e0592eeeac901b90e8de2cf5b67')

    def test_clone_at_head(self):
        git = vcs.GitHelper('git')
        self.assertEqual(git.clone('git.clone1', 'a7af835862da0e0592eeeac901b90e8de2cf5b67'), 'a7af835862da0e0592eeeac901b90e8de2cf5b67')

    def test_clone_at_head_1(self):
        git = vcs.GitHelper('git')
        self.assertEqual(git.clone('git.clone1', '2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed'), '2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed')
        self.assertEqual(git.clone('git.clone2', '2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed'), '2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed')

    def test_non_existing_git(self):
        git = vcs.GitHelper('does_not_exists')
        self.assertRaises(InfrastructureError, git.clone, ('foo.bar'))

    def test_existing_destination(self):
        git = vcs.GitHelper('git')
        self.assertEqual(git.clone('git.clone1'), 'a7af835862da0e0592eeeac901b90e8de2cf5b67')
        self.assertRaises(InfrastructureError, git.clone, ('git.clone1'))
        self.assertRaises(InfrastructureError, git.clone, ('git'))

    def test_invalid_commit(self):
        git = vcs.GitHelper('git')
        self.assertRaises(InfrastructureError, git.clone, 'foo.bar', 'badhash')


class TestBzr(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        self.cwd = os.getcwd()

        # Go into a temp dirctory
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)
        self.env = {'BZR_HOME': '/dev/null', 'BZR_LOG': '/dev/null'}

        # Create a Git repository with two commits
        subprocess.check_output(['bzr', 'init', 'repo'], env=self.env, stderr=subprocess.STDOUT)
        os.chdir('repo')
        with open('test.txt', 'w') as datafile:
            datafile.write("Some data")
        subprocess.check_output(['bzr', 'add', 'test.txt'], env=self.env, stderr=subprocess.STDOUT)
        subprocess.check_output(['bzr', 'commit', 'test.txt', '-m', 'First commit'],
                                env=self.env, stderr=subprocess.STDOUT)
        with open('second.txt', 'w') as datafile:
            datafile.write("Some more data")
        subprocess.check_output(['bzr', 'add', 'second.txt'], stderr=subprocess.STDOUT)
        subprocess.check_output(['bzr', 'commit', 'second.txt', '-m', 'Second commit'],
                                env=self.env, stderr=subprocess.STDOUT)

        # Go into the tempdir
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.cwd)
        # Remove everything
        shutil.rmtree(self.tmpdir)

    def test_simple_clone(self):
        bzr = vcs.BzrHelper('repo')
        self.assertEqual(bzr.clone('bzr.clone1'), '2')
        self.assertEqual(bzr.clone('bzr.clone2'), '2')
        self.assertEqual(bzr.clone('bzr.clone3'), '2')

    def test_clone_at_2(self):
        bzr = vcs.BzrHelper('repo')
        self.assertEqual(bzr.clone('bzr.clone1', '2'), '2')

    def test_clone_at_1(self):
        bzr = vcs.BzrHelper('repo')
        self.assertEqual(bzr.clone('bzr.clone1', '1'), '1')
        self.assertEqual(bzr.clone('bzr.clone2', '1'), '1')

    def test_non_existing_bzr(self):
        bzr = vcs.BzrHelper('does_not_exists')
        self.assertRaises(InfrastructureError, bzr.clone, ('foo.bar'))

    def test_existing_destination(self):
        bzr = vcs.BzrHelper('repo')
        self.assertEqual(bzr.clone('bzr.clone1'), '2')
        self.assertRaises(InfrastructureError, bzr.clone, ('bzr.clone1'))
        self.assertRaises(InfrastructureError, bzr.clone, ('repo'))

    def test_invalid_commit(self):
        bzr = vcs.BzrHelper('repo')
        self.assertRaises(InfrastructureError, bzr.clone, 'foo.bar', '3')
        self.assertRaises(InfrastructureError, bzr.clone, 'foo.bar', 'badrev')


class TestConstants(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """
    Tests that constants set in the Job YAML as parameters in an Action stanza
    override the value of that constant set in the python code for each action
    in that stanza.
    """
    def setUp(self):
        super(TestConstants, self).setUp()
        factory = Factory()
        self.job = factory.create_bbb_job('sample_jobs/uboot-ramdisk.yaml', mkdtemp())
        self.assertIsNotNone(self.job)

    def test_action_parameters(self):
        self.assertIsNotNone(self.job.parameters)
        deploy = self.job.pipeline.actions[0]
        self.assertIsNone(deploy.parameters.get('parameters', None))
        uboot = self.job.pipeline.actions[1]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            uboot.parameters.get('parameters', {}).get('shutdown-message', SHUTDOWN_MESSAGE)
        )
        self.assertIsInstance(uboot, UBootAction)
        retry = uboot.internal_pipeline.actions[3]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            retry.parameters['parameters'].get('shutdown-message', SHUTDOWN_MESSAGE)
        )
        self.assertIsInstance(retry, UBootRetry)
        reset = retry.internal_pipeline.actions[0]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            reset.parameters['parameters'].get('shutdown-message', SHUTDOWN_MESSAGE)
        )
        self.assertIsInstance(reset, ResetDevice)
        reboot = reset.internal_pipeline.actions[0]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            reboot.parameters['parameters'].get('shutdown-message', SHUTDOWN_MESSAGE)
        )
        self.assertIsInstance(reboot, RebootDevice)
        self.assertIsNotNone(reboot.parameters.get('parameters'))
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            reboot.parameters['parameters'].get('shutdown-message', SHUTDOWN_MESSAGE)
        )
