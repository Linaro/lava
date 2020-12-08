import pytest


from lava_dispatcher_host import share_device_with_container_lxc
from lava_dispatcher_host import share_device_with_container_docker


@pytest.fixture(autouse=True)
def check_call(mocker):
    return mocker.patch("subprocess.check_call")


@pytest.fixture(autouse=True)
def call(mocker):
    return mocker.patch("subprocess.call")


@pytest.fixture(autouse=True)
def check_output(mocker):
    return mocker.patch("subprocess.check_output")


@pytest.fixture(autouse=True)
def stat(mocker):
    s = mocker.patch("os.stat")
    ret = s.return_value
    ret.st_uid = 999
    ret.st_gid = 999
    ret.st_mode = 0o664
    ret.st_rdev = 0xBD02
    return s


class TestLXC:
    def test_simple_sharing(self, check_call, mocker):
        dev = "/dev/bus/usb/001/001"
        share_device_with_container_lxc("container", dev)
        assert check_call.call_args_list == [
            mocker.call(["lxc-device", "-n", "container", "add", dev]),
            mocker.call(
                [
                    "lxc-attach",
                    "-n",
                    "container",
                    "--",
                    "sh",
                    "-c",
                    f"chown 999:999 {dev} && chmod 664 {dev}",
                ]
            ),
        ]

    def test_links(self, check_call, pyudev, mocker):
        dev = "/dev/bus/usb/001/001"
        link = "/dev/ttyUSB1"
        pyudev.Devices.from_device_file.return_value.device_links = [link]
        share_device_with_container_lxc("container", dev)
        check_call.assert_any_call(
            [
                "lxc-attach",
                "-n",
                "container",
                "--",
                "sh",
                "-c",
                f"mkdir -p /dev && ln -f -s {dev} {link}",
            ]
        )


class TestDocker:
    def test_simple_sharing(self, call, mocker):
        mocker.patch("lava_dispatcher_host.open", mocker.mock_open())
        dev = "/dev/bus/usb/001/001"
        share_device_with_container_docker("container", dev)
        assert call.call_args_list == [
            mocker.call(
                [
                    "docker",
                    "exec",
                    "container",
                    "sh",
                    "-c",
                    f"mkdir -p /dev/bus/usb/001 && mknod {dev} c 189 2 && chown 999:999 {dev} && chmod 664 {dev}",
                ]
            )
        ]

    def test_links(self, call, mocker, pyudev):
        mocker.patch("lava_dispatcher_host.open", mocker.mock_open())
        dev = "/dev/bus/usb/001/001"
        link = "/dev/ttyUSB1"
        pyudev.Devices.from_device_file.return_value.device_links = [link]
        share_device_with_container_docker("container", dev)
        call.assert_called_with(
            [
                "docker",
                "exec",
                "container",
                "sh",
                "-c",
                f"mkdir -p /dev && ln -f -s {dev} {link}",
            ]
        )
