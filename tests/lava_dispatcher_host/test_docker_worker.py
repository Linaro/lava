import argparse
import pytest
import lava_dispatcher_host.docker_worker


@pytest.fixture
def get_image(mocker):
    return mocker.patch("lava_dispatcher_host.docker_worker.get_image")


@pytest.fixture
def check_call(mocker):
    return mocker.patch("lava_dispatcher_host.docker_worker.subprocess.check_call")


@pytest.fixture
def options(tmp_path):
    o = argparse.Namespace()
    o.worker_dir = tmp_path / "worker"
    return o


class TestGetImage:
    def test_image_exists(self, check_call, mocker):
        lava_dispatcher_host.docker_worker.get_image("foobar")
        check_call.assert_called_with(
            ["docker", "image", "inspect", "foobar"],
            stdout=mocker.ANY,
            stderr=mocker.ANY,
        )

    def test_image_missing(self, check_call, mocker):
        mocker.patch("lava_dispatcher_host.docker_worker.has_image", return_value=False)
        lava_dispatcher_host.docker_worker.get_image("foobar")
        check_call.assert_called_with(["docker", "pull", "foobar"])


class TestRun:
    def test_get_image_released(self, get_image, check_call, options):
        lava_dispatcher_host.docker_worker.run("2020.07", options)
        get_image.assert_called_with("lavasoftware/lava-dispatcher:2020.07")

    def test_get_image_development(self, get_image, check_call, options):
        lava_dispatcher_host.docker_worker.run("2020.07.10.g12371263", options)
        get_image.assert_called_with(
            "hub.lavasoftware.org/lava/lava/amd64/lava-dispatcher:2020.07.10.g12371263"
        )
