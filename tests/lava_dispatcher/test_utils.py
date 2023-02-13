# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Remi Duraffort remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import subprocess  # nosec - unit test support.
import unittest

import pytest

from lava_common.exceptions import InfrastructureError, JobError
from lava_common.utils import debian_filename_version
from lava_dispatcher.action import Action

# pylint: disable=unused-import
from lava_dispatcher.actions.boot import strategies as boot_strategies
from lava_dispatcher.actions.deploy import strategies as deploy_strategies
from lava_dispatcher.actions.test import strategies as test_strategies
from lava_dispatcher.utils import installers, vcs
from lava_dispatcher.utils.decorator import replace_exception
from lava_dispatcher.utils.shell import which
from tests.utils import infrastructure_error


@pytest.fixture
def setup(tmp_path):
    os.chdir(str(tmp_path))

    # Create a Git repository with two commits
    subprocess.check_output(["git", "init", "git"])  # nosec - unit test support.
    os.chdir("git")
    subprocess.check_output(
        ["git", "checkout", "-b", "master"]
    )  # nosec - unit test support.
    with open("test.txt", "w") as testfile:
        testfile.write("Some data")
    subprocess.check_output(["git", "add", "test.txt"])  # nosec - unit test support.
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
    subprocess.check_output(["git", "add", "second.txt"])  # nosec - unit test support.
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
    subprocess.check_output(["git", "add", "third.txt"])  # nosec - unit test support.
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


def test_simple_clone(setup):
    git = vcs.GitHelper("git")
    assert git.clone("git.clone1") == "a7af835862da0e0592eeeac901b90e8de2cf5b67"
    assert git.clone("git.clone2") == "a7af835862da0e0592eeeac901b90e8de2cf5b67"
    assert git.clone("git.clone3") == "a7af835862da0e0592eeeac901b90e8de2cf5b67"


def test_clone_at_head(setup):
    git = vcs.GitHelper("git")
    assert (
        git.clone("git.clone1", revision="a7af835862da0e0592eeeac901b90e8de2cf5b67")
        == "a7af835862da0e0592eeeac901b90e8de2cf5b67"
    )


def test_clone_at_head_1(setup):
    git = vcs.GitHelper("git")
    assert (
        git.clone("git.clone1", revision="2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed")
        == "2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed"
    )
    assert (
        git.clone("git.clone2", revision="2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed")
        == "2f83e6d8189025e356a9563b8d78bdc8e2e9a3ed"
    )


def test_non_existing_git(setup):
    git = vcs.GitHelper("does_not_exists")
    with pytest.raises(InfrastructureError):
        git.clone("foo.bar")


def test_existing_destination(setup):
    git = vcs.GitHelper("git")
    assert git.clone("git.clone1") == "a7af835862da0e0592eeeac901b90e8de2cf5b67"
    with pytest.raises(InfrastructureError):
        git.clone("git.clone1")
    with pytest.raises(InfrastructureError):
        git.clone("git")


def test_invalid_commit(setup):
    git = vcs.GitHelper("git")
    with pytest.raises(InfrastructureError):
        git.clone("foo.bar", True, "badhash")


def test_branch(setup, tmp_path):
    git = vcs.GitHelper("git")
    assert (
        git.clone("git.clone1", branch="testing")
        == "f2589a1b7f0cfc30ad6303433ba4d5db1a542c2d"
    )
    assert (tmp_path / "git.clone1" / ".git").exists()


def test_no_history(setup, tmp_path):
    git = vcs.GitHelper("git")
    assert (
        git.clone("git.clone1", history=False)
        == "a7af835862da0e0592eeeac901b90e8de2cf5b67"
    )
    assert not (tmp_path / "git.clone1" / ".git").exists()


ALLOWED = ["commands", "deploy", "test"]


def test_summary_exists():
    for subclass in Action.__subclasses__():
        # TODO: is this normal?
        if not hasattr(subclass, "name"):
            continue
        if subclass.name not in ALLOWED:
            assert hasattr(subclass, "summary")


def test_description_exists():
    for subclass in Action.__subclasses__():
        if not hasattr(subclass, "name"):
            continue
        if subclass.name not in ALLOWED:
            assert hasattr(subclass, "description")


@replace_exception(RuntimeError, JobError)
def replacement(msg):
    raise RuntimeError(msg)


@replace_exception(RuntimeError, JobError, limit=1024)
def short_replacement(msg):
    raise RuntimeError(msg)


def test_replacement():
    with pytest.raises(JobError):
        replacement("test")


def test_long_replacement():
    with pytest.raises(JobError) as exc:
        replacement("t" * 4056)
    assert len(str(exc.value)) == 2048


def test_short_replacement():
    with pytest.raises(JobError) as exc:
        short_replacement("t" * 4096)
    assert len(str(exc.value)) == 1024


def test_installer_add_late_command(tmp_path):
    os.chdir(str(tmp_path))
    # Create preseed file with a few lines.
    with open("preseed.cfg", "w") as preseedfile:
        preseedfile.write("d-i netcfg/dhcp_timeout string 60\n")
        preseedfile.write("d-i pkgsel/include string openssh-server build-essential\n")
        preseedfile.write("d-i finish-install/reboot_in_progress note\n")
    preseedfile = "preseed.cfg"

    # Test adding new preseed/late_command line.
    extra_command = "cmd1"
    installers.add_late_command(preseedfile, extra_command)
    with open("preseed.cfg") as f_in:
        file_content = f_in.read()
        assert "d-i preseed/late_command string cmd1" in file_content

    # Test appending the second command to existing presseed/late_command line.
    extra_command = "cmd2 ;"
    installers.add_late_command(preseedfile, extra_command)
    with open("preseed.cfg") as f_in:
        file_content = f_in.read()
        assert "d-i preseed/late_command string cmd1; cmd2 ;" in file_content

    # Test if it strips off extra space and semi-colon.
    extra_command = "cmd3"
    installers.add_late_command(preseedfile, extra_command)
    with open("preseed.cfg") as f_in:
        file_content = f_in.read()
        assert "d-i preseed/late_command string cmd1; cmd2; cmd3" in file_content


@unittest.skipIf(infrastructure_error("dpkg-query"), "dpkg-query not installed")
def test_dpkg():
    # avoid checking the actual version
    binary = which("dpkg-query")
    assert debian_filename_version(binary) is not None
