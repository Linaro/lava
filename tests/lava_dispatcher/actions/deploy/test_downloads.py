# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.


import pytest
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.downloads import PostprocessWithDocker
from lava_dispatcher.actions.deploy.downloads import DownloadsAction
from lava_dispatcher.job import Job
from tests.lava_dispatcher.test_basic import Factory


@pytest.fixture
def job(tmpdir):
    job = Job(1234, {}, None)
    return job


def test_downloads_action(job):
    action = DownloadsAction()
    action.level = 2
    action.job = job
    action.populate(
        {
            "images": {"rootfs": {"url": "https://example.com/image.img"}},
            "namespace": "common",
        }
    )
    download = action.pipeline.actions[0]
    assert isinstance(download, DownloaderAction)
    assert download.key == "rootfs"
    assert str(download.path) == f"{job.tmp_dir}/downloads/common"
    assert download.params == {"url": "https://example.com/image.img"}


def test_downloads_action_adds_docker_action():
    factory = Factory()
    factory.validate_job_strict = True
    job = factory.create_job(
        "qemu01.jinja2", "sample_jobs/qemu-download-postprocess.yaml"
    )

    deploy = job.pipeline.actions[0]
    action = deploy.pipeline.actions[-1]
    assert isinstance(action, PostprocessWithDocker)
    assert str(action.path) == f"{job.tmp_dir}/downloads/common"


@pytest.fixture
def action(tmpdir):
    action = PostprocessWithDocker(tmpdir)
    action.populate(
        {
            "postprocess": {
                "docker": {"image": "foo", "steps": ["date", "echo HELLO WORLD"]}
            }
        }
    )
    return action


def test_postprocess_with_docker_populate(action):
    assert action.image == "foo"
    assert "date" in action.steps
    assert "echo HELLO WORLD" in action.steps


def test_postprocess_with_docker_populate_missing_data(tmpdir):
    action = PostprocessWithDocker(tmpdir)
    action.populate({})


def test_postprocess_with_docker_validate(tmpdir):
    action = PostprocessWithDocker(tmpdir)
    assert not action.validate()
    assert "docker image name missing" in action.errors
    assert "postprocessing steps missing" in action.errors
    action.image = "foobar"
    action.steps = ["date"]
    action.errors.clear()
    assert action.validate()
    assert len(action.errors) == 0


def test_postprocess_with_docker_run(action, job, mocker):
    action.job = job

    run = mocker.patch("lava_dispatcher.utils.docker.DockerRun.run")

    origconn = mocker.MagicMock()
    conn = action.run(origconn, 4242)

    assert conn is origconn

    script = action.path / "postprocess.sh"
    assert script.exists()
    script_text = script.read_text()
    assert "date\n" in script_text
    assert "echo HELLO WORLD\n" in script_text

    run.assert_called_with(mocker.ANY, action=action)
