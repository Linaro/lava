# Copyright (C) 2014-2019 Linaro Limited
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
import subprocess  # nosec - unit test support.
import tempfile
import unittest

from lava_dispatcher.tests.test_uboot import UBootFactory, StdoutTestCase
from lava_dispatcher.actions.boot.u_boot import UBootAction, UBootRetry
from lava_dispatcher.power import ResetDevice, PDUReboot
from lava_dispatcher.tests.utils import infrastructure_error
from lava_common.exceptions import InfrastructureError, JobError
from lava_common.utils import debian_filename_version
from lava_dispatcher.action import Action
from lava_dispatcher.utils import vcs, installers
from lava_dispatcher.utils.decorator import replace_exception
from lava_dispatcher.utils.shell import which


class TestGit(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.cwd = os.getcwd()

        # Go into a temp dirctory
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

        # Create a Git repository with two commits
        subprocess.check_output(["git", "init", "git"])  # nosec - unit test support.
        os.chdir("git")
        with open("test.txt", "w") as testfile:
            testfile.write("Some data")
        subprocess.check_output(  # nosec - unit test support.
            ["git", "add", "test.txt"]
        )
        subprocess.check_output(  # nosec - unit test support.
            ["git", "commit", "test.txt", "-m", "First commit"],
            env={
                "GIT_COMMITTER_DATE": "Fri Oct 24 14:40:36 CEST 2014",
                "GIT_AUTHOR_DATE": "Fri Oct 24 14:40:36 CEST 2014",
                "GIT_AUTHOR_NAME": "Foo Bar",
                "GIT_AUTHOR_EMAIL": "foo@example.com",
                "GIT_COMMITTER_NAME": "Foo Bar",
                "GIT_COMMITTER_EMAIL": "foo@example.com",
            },
        )
        with open("second.txt", "w") as datafile:
            datafile.write("Some more data")
        subprocess.check_output(  # nosec - unit test support.
            ["git", "add", "second.txt"]
        )
        subprocess.check_output(  # nosec - unit test support.
            ["git", "commit", "second.txt", "-m", "Second commit"],
            env={
                "GIT_COMMITTER_DATE": "Fri Oct 24 14:40:38 CEST 2014",
                "GIT_AUTHOR_DATE": "Fri Oct 24 14:40:38 CEST 2014",
                "GIT_AUTHOR_NAME": "Foo Bar",
                "GIT_AUTHOR_EMAIL": "foo@example.com",
                "GIT_COMMITTER_NAME": "Foo Bar",
                "GIT_COMMITTER_EMAIL": "foo@example.com",
            },
        )

        subprocess.check_output(  # nosec - unit test support.
            ["git", "checkout", "-q", "-b", "testing"]
        )
        with open("third.txt", "w") as datafile:
            datafile.write("333")
        subprocess.check_output(  # nosec - unit test support.
            ["git", "add", "third.txt"]
        )
        subprocess.check_output(  # nosec - unit test support.
            ["git", "commit", "third.txt", "-m", "Third commit"],
            env={
                "GIT_COMMITTER_DATE": "Thu Sep  1 10:14:29 CEST 2016",
                "GIT_AUTHOR_DATE": "Thu Sep  1 10:14:29 CEST 2016",
                "GIT_AUTHOR_NAME": "Foo Bar",
                "GIT_AUTHOR_EMAIL": "foo@example.com",
                "GIT_COMMITTER_NAME": "Foo Bar",
                "GIT_COMMITTER_EMAIL": "foo@example.com",
            },
        )

        subprocess.check_output(  # nosec - unit test support.
            ["git", "checkout", "-q", "master"]
        )

        # Go into the tempdir
        os.chdir("..")

    def tearDown(self):
        os.chdir(self.cwd)
        # Remove everything
        shutil.rmtree(self.tmpdir)

    def test_simple_clone(self):
        git = vcs.GitHelper("git")
        self.assertEqual(
            git.clone("git.clone1"), "a7af835862da0e0592eeeac901b90e8de2cf5b67"
        )
        self.assertEqual(
            git.clone("git.clone2"), "a7af835862da0e0592eeeac901b90e8de2cf5b67"
        )
        self.assertEqual(
            git.clone("git.clone3"), "a7af835862da0e0592eeeac901b90e8de2cf5b67"
        )

    def test_clone_at_head(self):
        git = vcs.GitHelper("git")
        self.assertEqual(
            git.clone(
                "git.clone1", revision="a7af835862da0e0592eeeac901b90e8de2cf5b67"
            ),
            "a7af835862da0e0592eeeac901b90e8de2cf5b67",
        )

    def test_clone_at_head_1(self):
        git = vcs.GitHelper("git")
        self.assertEqual(
            git.clone(
                "git.clone1", revision="2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed"
            ),
            "2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed",
        )
        self.assertEqual(
            git.clone(
                "git.clone2", revision="2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed"
            ),
            "2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed",
        )

    def test_non_existing_git(self):
        git = vcs.GitHelper("does_not_exists")
        self.assertRaises(InfrastructureError, git.clone, ("foo.bar"))

    def test_existing_destination(self):
        git = vcs.GitHelper("git")
        self.assertEqual(
            git.clone("git.clone1"), "a7af835862da0e0592eeeac901b90e8de2cf5b67"
        )
        self.assertRaises(InfrastructureError, git.clone, ("git.clone1"))
        self.assertRaises(InfrastructureError, git.clone, ("git"))

    def test_invalid_commit(self):
        git = vcs.GitHelper("git")
        self.assertRaises(InfrastructureError, git.clone, "foo.bar", True, "badhash")

    def test_branch(self):
        git = vcs.GitHelper("git")
        self.assertEqual(
            git.clone("git.clone1", branch="testing"),
            "f2589a1b7f0cfc30ad6303433ba4d5db1a542c2d",
        )
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, "git.clone1", ".git")))

    def test_no_history(self):
        git = vcs.GitHelper("git")
        self.assertEqual(
            git.clone("git.clone1", history=False),
            "a7af835862da0e0592eeeac901b90e8de2cf5b67",
        )
        self.assertFalse(
            os.path.exists(os.path.join(self.tmpdir, "git.clone1", ".git"))
        )


class TestConstants(StdoutTestCase):
    """
    Tests that constants set in the Job YAML as parameters in an Action stanza
    override the value of that constant set in the python code for each action
    in that stanza.
    """

    def setUp(self):
        super().setUp()
        factory = UBootFactory()
        self.job = factory.create_bbb_job("sample_jobs/uboot-ramdisk.yaml")
        self.assertIsNotNone(self.job)

    def test_action_parameters(self):
        self.assertIsNotNone(self.job.parameters)
        deploy = self.job.pipeline.actions[0]
        self.assertIsNone(deploy.parameters.get("parameters"))
        uboot = self.job.pipeline.actions[1]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            uboot.parameters.get("parameters", {}).get(
                "shutdown-message", self.job.device.get_constant("shutdown-message")
            ),
        )
        self.assertIsInstance(uboot, UBootAction)
        retry = [
            action
            for action in uboot.internal_pipeline.actions
            if action.name == "uboot-retry"
        ][0]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            retry.parameters["parameters"].get(
                "shutdown-message", self.job.device.get_constant("shutdown-message")
            ),
        )
        self.assertIsInstance(retry, UBootRetry)
        reset = retry.internal_pipeline.actions[0]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            reset.parameters["parameters"].get(
                "shutdown-message", self.job.device.get_constant("shutdown-message")
            ),
        )
        self.assertIsInstance(reset, ResetDevice)
        reboot = reset.internal_pipeline.actions[0]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            reboot.parameters["parameters"].get(
                "shutdown-message", self.job.device.get_constant("shutdown-message")
            ),
        )
        self.assertIsInstance(reboot, PDUReboot)
        self.assertIsNotNone(reboot.parameters.get("parameters"))
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            reboot.parameters["parameters"].get(
                "shutdown-message", self.job.device.get_constant("shutdown-message")
            ),
        )


class TestClasses(StdoutTestCase):
    def setUp(self):
        super().setUp()
        from lava_dispatcher.actions.deploy import (  # pylint: disable=reimported
            strategies,
        )
        from lava_dispatcher.actions.boot import (  # pylint: disable=reimported
            strategies,
        )
        from lava_dispatcher.actions.test import (  # pylint: disable=reimported
            strategies,
        )

        self.allowed = ["commands", "deploy", "test"]  # pipeline.actions.commands.py

    def test_summary_exists(self):
        for subclass in Action.__subclasses__():
            if not hasattr(subclass, "name"):
                continue
            if not hasattr(subclass, "summary") and subclass.name not in self.allowed:
                self.fail(subclass)

    def test_description_exists(self):
        for subclass in Action.__subclasses__():
            if not hasattr(subclass, "name"):
                continue
            if (
                not hasattr(subclass, "description")
                and subclass.name not in self.allowed
            ):
                self.fail(subclass)

    @replace_exception(RuntimeError, JobError)
    def replacement(self, msg):
        raise RuntimeError(msg)

    @replace_exception(RuntimeError, JobError, limit=1024)
    def short_replacement(self, msg):
        raise RuntimeError(msg)

    def test_replacement(self):
        try:
            self.replacement("test")
        except JobError:
            pass
        except RuntimeError:
            self.fail("decorator failed")
        except:  # noqa
            self.fail("Unexpected exception")

    def test_long_replacement(self):
        try:
            self.replacement("t" * 4056)
        except JobError as exc:
            self.assertEqual(len(str(exc)), 2048)
        except RuntimeError:
            self.fail("decorator failed")
        except:  # noqa
            self.fail("Unexpected exception")

    def test_short_replacement(self):
        try:
            self.short_replacement("t" * 4096)
        except JobError as exc:
            self.assertEqual(len(str(exc)), 1024)
        except RuntimeError:
            self.fail("decorator failed")
        except:  # noqa
            self.fail("Unexpected exception")


class TestInstallers(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmpdir)

    def test_add_late_command(self):
        # Create preseed file with a few lines.
        with open("preseed.cfg", "w") as preseedfile:
            preseedfile.write("d-i netcfg/dhcp_timeout string 60\n")
            preseedfile.write(
                "d-i pkgsel/include string openssh-server build-essential\n"
            )
            preseedfile.write("d-i finish-install/reboot_in_progress note\n")
        preseedfile = "preseed.cfg"

        # Test adding new preseed/late_command line.
        extra_command = "cmd1"
        installers.add_late_command(preseedfile, extra_command)
        with open("preseed.cfg") as f_in:
            file_content = f_in.read()
            self.assertTrue("d-i preseed/late_command string cmd1" in file_content)

        # Test appending the second command to existing presseed/late_command line.
        extra_command = "cmd2 ;"
        installers.add_late_command(preseedfile, extra_command)
        with open("preseed.cfg") as f_in:
            file_content = f_in.read()
            self.assertTrue(
                "d-i preseed/late_command string cmd1; cmd2 ;" in file_content
            )

        # Test if it strips off extra space and semi-colon.
        extra_command = "cmd3"
        installers.add_late_command(preseedfile, extra_command)
        with open("preseed.cfg") as f_in:
            file_content = f_in.read()
            self.assertTrue(
                "d-i preseed/late_command string cmd1; cmd2; cmd3" in file_content
            )


class TestVersions(StdoutTestCase):
    @unittest.skipIf(infrastructure_error("dpkg-query"), "dpkg-query not installed")
    def test_dpkg(self):
        # avoid checking the actual version
        binary = which("dpkg-query")
        self.assertIsNotNone(debian_filename_version(binary, label=True))
