import pytest
from lava_dispatcher.utils.docker import DockerRun


@pytest.fixture
def run():
    return DockerRun("foobar")


def test_basic(run):
    assert run.cmdline() == ["docker", "run", "--rm", "foobar"]


def test_hostname(run):
    run.hostname("blah")
    assert "--hostname=blah" in run.cmdline()


def test_workdir(run):
    run.workdir("/path/to/workdir")
    assert "--workdir=/path/to/workdir" in run.cmdline()


def test_interactive(run):
    run.interactive()
    cmdline = run.cmdline()
    assert "--interactive" in cmdline
    assert "--tty" in cmdline


def test_device(run, mocker):
    mocker.patch("pathlib.Path.exists", return_value=True)
    run.add_device("/dev/kvm")
    assert "--device=/dev/kvm" in run.cmdline()


def test_device_skip_missing(run, mocker):
    mocker.patch("pathlib.Path.exists", return_value=False)
    run.add_device("/dev/kvm", skip_missing=True)
    assert "--device=/dev/kvm" not in run.cmdline()


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
    opt = f"--mount=type=bind,source=/foo,destination=/foo,read_only=true"
    assert opt in run.cmdline()


def test_args(run):
    cmdline = run.cmdline("hostname", "--fqdn")
    assert cmdline[-2] == "hostname"
    assert cmdline[-1] == "--fqdn"
