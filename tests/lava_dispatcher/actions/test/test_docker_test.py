# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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

import pytest
import re
import time
from pathlib import Path
from tests.lava_dispatcher.test_basic import Factory


@pytest.fixture
def factory():
    return Factory()


@pytest.fixture
def job(factory):
    return factory.create_job(
        "hi6220-hikey-r2-01.jinja2", "sample_jobs/docker-test.yaml"
    )


@pytest.fixture
def action(job):
    return job.pipeline.actions[2]


@pytest.fixture
def first_test_action(action):
    return action


@pytest.fixture
def second_test_action(job):
    return job.pipeline.actions[3]


def test_validate_schema(factory):
    factory.validate_job_strict = True
    # The next call not crashing means that the strict schema validation
    # passed.
    factory.create_job("hi6220-hikey-r2-01.jinja2", "sample_jobs/docker-test.yaml")


def test_detect_correct_action(action):
    assert type(action).__name__ == "DockerTestAction"


def test_run(action, mocker):
    mocker.patch("lava_dispatcher.utils.containers.DockerDriver.__get_device_nodes__")
    ShellCommand = mocker.patch("lava_dispatcher.actions.test.docker.ShellCommand")
    ShellSesssion = mocker.patch("lava_dispatcher.actions.test.docker.ShellSession")
    docker_connection = mocker.MagicMock()
    ShellSesssion.return_value = docker_connection
    action_run = mocker.patch("lava_dispatcher.actions.test.docker.TestShellAction.run")
    connection = mocker.MagicMock()
    add_device_container_mappings = mocker.patch(
        "lava_dispatcher_host.action.DeviceContainerMappingMixin.add_device_container_mappings"
    )
    get_udev_devices = mocker.patch(
        "lava_dispatcher.actions.test.docker.get_udev_devices",
        return_value=["/dev/foobar"],
    )
    share_device_with_container_docker = mocker.patch(
        "lava_dispatcher.actions.test.docker.share_device_with_container_docker"
    )
    docker_wait = mocker.patch("lava_dispatcher.utils.docker.DockerRun.wait")
    docker_prepare = mocker.patch("lava_dispatcher.utils.docker.DockerRun.prepare")

    action.validate()
    action.run(connection, time.time() + 1000)

    # device is shared with the container
    add_device_container_mappings.assert_called()

    get_udev_devices.assert_called_with(
        device_info=[{"board_id": "0123456789"}], logger=mocker.ANY, required=False
    )

    # overlay gets created
    overlay = next(Path(action.job.tmp_dir).glob("lava-create-overlay-*/lava-*"))
    assert overlay.exists()
    # overlay gets the correct content
    lava_test_runner = overlay / "bin" / "lava-test-runner"
    assert lava_test_runner.exists()
    lava_test_0 = overlay / "0"
    assert lava_test_runner.exists()

    environmentfile = overlay / "environment"
    env = {
        re.sub(r"=.*$", "", l): re.sub("^[^=]*=", "", l)
        for l in environmentfile.open().read().splitlines()
    }
    assert env["export ANDROID_SERIAL"] == "0123456789"
    assert env["export LAVA_BOARD_ID"] == "0123456789"
    assert env["export LAVA_CONNECTION_COMMAND_UART0"] == "'telnet localhost 4002'"
    assert env["export LAVA_CONNECTION_COMMAND_UART1"] == "'telnet 192.168.1.200 8001'"
    # primary connection:
    assert env["export LAVA_CONNECTION_COMMAND"] == "'telnet 192.168.1.200 8001'"

    assert (
        env["export LAVA_HARD_RESET_COMMAND"] == "'/path/to/reset.sh 0 1 2 && sleep 5'"
    )
    assert env["export LAVA_POWER_ON_COMMAND"] == "'/path/to/power-on.sh 0 1 2'"
    assert env["export LAVA_POWER_OFF_COMMAND"] == "'/path/to/power-off.sh 0 1 2'"

    # docker gets called
    docker_call = ShellCommand.mock_calls[0][1][0]
    assert docker_call.startswith("docker run")
    # overlay gets passed into docker
    assert (
        re.match(
            r".* --mount=type=bind,source=%s,destination=/%s" % (overlay, overlay.name),
            docker_call,
        )
        is not None
    )

    # prepares container image
    docker_prepare.assert_called()

    # waits for container to be available
    docker_wait.assert_called()

    # device shared with docker
    share_device_with_container_docker.assert_called_with(mocker.ANY, "/dev/foobar")

    # the lava-test-shell implementation gets called with the docker shell
    action_run.assert_called_with(docker_connection, mocker.ANY)

    # the docker shell gets finalized
    docker_connection.finalise.assert_called()


def test_stages(first_test_action, second_test_action):
    assert first_test_action.parameters["stage"] == 0
    assert second_test_action.parameters["stage"] == 1


def test_docker_test_shell_validate(action):
    action.validate()
    assert action.valid == True
    [a.__errors__.clear() for a in action.pipeline.actions]

    action.job.parameters["dispatcher"]["test_docker_bind_mounts"] = [
        ["foo", "bar", "rw"]
    ]
    action.validate()
    assert action.valid == True
    [a.__errors__.clear() for a in action.pipeline.actions]

    action.job.parameters["dispatcher"]["test_docker_bind_mounts"] = [["foo"]]
    action.validate()
    assert action.valid == False
    [a.__errors__.clear() for a in action.pipeline.actions]

    action.job.parameters["dispatcher"]["test_docker_bind_mounts"] = [[["foo"], "bar"]]
    action.validate()
    assert action.valid == False
    [a.__errors__.clear() for a in action.pipeline.actions]

    action.job.parameters["dispatcher"]["test_docker_bind_mounts"] = [
        ["foo", "bar", "foo"]
    ]
    action.validate()
    assert action.valid == False
    [a.__errors__.clear() for a in action.pipeline.actions]
