import subprocess
from unittest.mock import call

import pytest

from lava_dispatcher.utils.docker import DockerRun


@pytest.fixture
def run():
    return DockerRun("foobar")


def test_basic(run):
    assert run.cmdline() == ["docker", "run", "--rm", "--init", "foobar"]


def test_name(run):
    run.name("blah")
    assert "--name=blah" in run.cmdline()


def test_network(run):
    run.network("foo")
    assert "--network=container:foo" in run.cmdline()


def test_network_with_suffix(run):
    run.network("foo")
    run.suffix("bar")
    assert "--network=container:foobar" in run.cmdline()


def test_workdir(run):
    run.workdir("/path/to/workdir")
    assert "--workdir=/path/to/workdir" in run.cmdline()


def test_interactive(run):
    run.interactive()
    cmdline = run.cmdline()
    assert "--interactive" in cmdline


def test_tty(run):
    run.tty()
    cmdline = run.cmdline()
    assert "--tty" in cmdline


def test_device(run, mocker):
    mocker.patch("pathlib.Path.exists", return_value=True)
    run.add_device("/dev/kvm")
    assert "--device=/dev/kvm" in run.cmdline()


def test_device_skip_missing(run, mocker):
    mocker.patch("pathlib.Path.exists", return_value=False)
    run.add_device("/dev/kvm", skip_missing=True)
    assert "--device=/dev/kvm" not in run.cmdline()


def test_device_skip_with_colon(run, mocker):
    mocker.patch("pathlib.Path.exists", return_value=False)
    run.add_device("/dev/serial/by-path/xxx:yyyy:zzzz")
    assert "--device=/dev/serial/by-path/xxx:yyyy:zzzz" not in run.cmdline()


def test_bind_mount(run):
    p = "/path/to/data"
    run.bind_mount(p)
    opt = f"--mount=type=bind,source={p},destination={p}"
    assert opt in run.cmdline()


def test_bind_mount_source_destination(run):
    run.bind_mount("/foo", "/bar")
    opt = f"--mount=type=bind,source=/foo,destination=/bar"
    assert opt in run.cmdline()


def test_bind_mount_read_only(run):
    run.bind_mount("/foo", None, True)
    opt = f"--mount=type=bind,source=/foo,destination=/foo,readonly=true"
    assert opt in run.cmdline()


def test_environment(run):
    run.environment("FOO", "BAR")
    cmdline = run.cmdline()
    assert "--env=FOO=BAR" in cmdline


def test_args(run):
    cmdline = run.cmdline("hostname", "--fqdn")
    assert cmdline[-2] == "hostname"
    assert cmdline[-1] == "--fqdn"


def test_run_architecture_check_failure(mocker):
    def results(cmd, *args, **kwargs):
        if cmd == ["arch"]:
            return "aarch64\n"
        elif cmd == ["docker", "inspect", "--format", "{{.Architecture}}", "myimage"]:
            return "x86_64\n"
        else:
            raise RuntimeError(f"Unexpected mock call: {cmd}")

    check_output = mocker.patch("subprocess.check_output", side_effect=results)
    getLogger = mocker.patch("logging.getLogger")
    logger = getLogger.return_value
    action = mocker.MagicMock()

    action = mocker.MagicMock()
    docker = DockerRun("myimage")
    docker.run("date", action=action)

    check_output.assert_any_call(["arch"], text=True)
    check_output.assert_any_call(
        ["docker", "inspect", "--format", "{{.Architecture}}", "myimage"], text=True
    )
    assert action.run_cmd.call_args_list == [
        call(["docker", "pull", "myimage"]),
        call(["docker", "run", "--rm", "--init", "myimage", "date"]),
    ]

    getLogger.assert_called_with("dispatcher")
    logger.warning.assert_called()


def test_run_architecture_check_success(mocker):
    check_output = mocker.patch("subprocess.check_output", return_value="xyz\n")
    getLogger = mocker.patch("logging.getLogger")
    logger = getLogger.return_value
    action = mocker.MagicMock()

    action = mocker.MagicMock()
    docker = DockerRun("myimage")
    docker.run("echo", action=action)  # no crash = success

    check_output.assert_any_call(["arch"], text=True)
    check_output.assert_any_call(
        ["docker", "inspect", "--format", "{{.Architecture}}", "myimage"], text=True
    )
    assert action.run_cmd.call_args_list == [
        call(["docker", "pull", "myimage"]),
        call(["docker", "run", "--rm", "--init", "myimage", "echo"]),
    ]
    logger.warning.assert_not_called()


def test_run_with_action(mocker):
    check_arch = mocker.patch(
        "lava_dispatcher.utils.docker.DockerRun.__check_image_arch__"
    )
    action = mocker.MagicMock()

    docker = DockerRun("myimage")
    docker.run("date", action=action)

    check_arch.assert_called()
    action.run_cmd.assert_has_calls(
        [
            mocker.call(["docker", "pull", "myimage"]),
            mocker.call(["docker", "run", "--rm", "--init", "myimage", "date"]),
        ]
    )


def test_run_with_local_image_does_not_pull(mocker):
    mocker.patch("lava_dispatcher.utils.docker.DockerRun.__check_image_arch__")
    docker = DockerRun("myimage")
    docker.local(True)
    action = mocker.MagicMock()
    action.run_cmd.return_value = 0
    docker.run("date", action=action)
    action.run_cmd.assert_has_calls(
        [
            mocker.call(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    "Image myimage exists locally",
                    "myimage",
                ],
                allow_fail=True,
            ),
            mocker.call(["docker", "run", "--rm", "--init", "myimage", "date"]),
        ]
    )


def test_run_with_local_image_does_not_pull_when_missing(mocker):
    mocker.patch("lava_dispatcher.utils.docker.DockerRun.__check_image_arch__")
    docker = DockerRun("myimage")
    docker.local(True)
    action = mocker.MagicMock()
    action.run_cmd.return_value = 1
    docker.run("date", action=action)
    action.run_cmd.assert_has_calls(
        [
            mocker.call(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    "Image myimage exists locally",
                    "myimage",
                ],
                allow_fail=True,
            ),
            mocker.call(["docker", "pull", "myimage"]),
            mocker.call(["docker", "run", "--rm", "--init", "myimage", "date"]),
        ]
    )


def test_from_parameters_image(mocker):
    job = mocker.MagicMock()
    assert DockerRun.from_parameters({"image": "foo"}, job).image == "foo"
    assert not DockerRun.from_parameters({"image": "foo"}, job).__local__
    assert DockerRun.from_parameters({"image": "foo", "local": True}, job).__local__


def test_from_parameters_suffix(mocker):
    job = mocker.MagicMock()
    job.job_id = "123"
    docker_run = DockerRun.from_parameters({"image": "foo"}, job)
    assert docker_run.__suffix__ == "-lava-123"


def test_from_parameters_name_network(mocker):
    job = mocker.MagicMock()
    job.job_id = "123"
    docker_run = DockerRun.from_parameters(
        {
            "image": "foo",
            "container_name": "foocontainer",
            "network_from": "othercontainer",
        },
        job,
    )
    assert docker_run.__name__ == "foocontainer-lava-123"
    assert docker_run.__network__ == "othercontainer"


def test_wait(mocker):
    docker = DockerRun("myimage")
    docker.name("foobar")

    sleep = mocker.patch("time.sleep")
    inspect = mocker.patch(
        "subprocess.check_call",
        side_effect=[
            subprocess.CalledProcessError(
                1, ["docker", "inspect", "--format=.", "foobar"]
            ),
            None,
        ],
    )
    docker.wait()
    call = mocker.call(
        ["docker", "inspect", mocker.ANY, "foobar"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    inspect.assert_has_calls([call, call])
    sleep.assert_called_once()
