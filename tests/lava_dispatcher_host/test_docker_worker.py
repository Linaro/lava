import argparse
import platform
import subprocess

import pytest
import lava_dispatcher_host.docker_worker


@pytest.fixture
def get_image(mocker):
    return mocker.patch("lava_dispatcher_host.docker_worker.get_image")


@pytest.fixture
def check_output(mocker):
    return mocker.patch("lava_dispatcher_host.docker_worker.subprocess.check_output")


@pytest.fixture
def Popen(mocker):
    return mocker.patch("lava_dispatcher_host.docker_worker.subprocess.Popen")


@pytest.fixture
def options(tmp_path):
    o = argparse.Namespace()
    o.worker_dir = tmp_path / "worker"
    o.build_dir = tmp_path / "build"
    o.name = "worker"
    o.url = "http://localhost"
    o.ws_url = None
    o.http_timeout = 600
    o.ping_interval = 20
    o.job_log_interval = 5
    o.username = None
    o.token = None
    o.token_file = None

    return o


class TestGetImage:
    def test_image_exists(self, check_output, mocker):
        popen = mocker.patch("lava_dispatcher_host.docker_worker.subprocess.Popen")
        assert lava_dispatcher_host.docker_worker.get_image("foobar") is True
        check_output.assert_called_with(
            ["docker", "image", "inspect", "foobar"],
            stderr=mocker.ANY,
        )

    def test_image_missing(self, check_output, mocker):
        mocker.patch("lava_dispatcher_host.docker_worker.has_image", return_value=False)
        assert lava_dispatcher_host.docker_worker.get_image("foobar") is True
        check_output.assert_called_with(
            ["docker", "pull", "foobar"], stderr=subprocess.STDOUT
        )


class TestBuildImage:
    def test_missing_dockerfile(self, tmp_path, check_output, mocker):
        image = "lavasoftware/lava-dispatcher:2021.08"
        build_dir = tmp_path / "build"
        build_dir.mkdir()

        lava_dispatcher_host.docker_worker.build_customized_image(image, build_dir)
        check_output.assert_not_called()

    def test_build_customized_image(self, tmp_path, check_output, mocker):
        original_image = "lavasoftware/lava-dispatcher:2021.05"
        image = "lavasoftware/lava-dispatcher:2021.08"
        tag = f"{image}.customized"

        build_dir = tmp_path / "build"
        build_dir.mkdir()
        dockerfile = build_dir / "Dockerfile"
        dockerfile.write_text(f"{original_image}\nRUN echo test > /test")

        lava_dispatcher_host.docker_worker.build_customized_image(image, build_dir)

        dockerfile_lava = build_dir / "Dockerfile.lava"
        assert dockerfile_lava.exists()
        content = dockerfile_lava.read_text()
        assert f"FROM {image}" in content
        assert f"FROM {original_image}" not in content

        check_output.assert_called_with(
            ["docker", "build", "--force-rm", "-f", "Dockerfile.lava", "-t", tag, "."],
            cwd=build_dir,
        )


class TestRun:
    def test_get_image_released(self, get_image, Popen, options, mocker):
        mocker.patch("time.sleep")
        lava_dispatcher_host.docker_worker.run("2020.07", options)
        get_image.assert_called_with("lavasoftware/lava-dispatcher:2020.07")
        lava_dispatcher_host.docker_worker.run("2020.07.1", options)
        get_image.assert_called_with("lavasoftware/lava-dispatcher:2020.07.1")

    def test_get_image_development(self, get_image, Popen, options, mocker):
        mocker.patch("time.sleep")
        lava_dispatcher_host.docker_worker.run("2020.07.0010.g12371263", options)
        if platform.machine() == "x86_64":
            get_image.assert_called_with(
                "hub.lavasoftware.org/lava/lava/amd64/lava-dispatcher:2020.07.0010.g12371263"
            )
        elif platform.machine() == "aarch64":
            get_image.assert_called_with(
                "hub.lavasoftware.org/lava/lava/aarch64/lava-dispatcher:2020.07.0010.g12371263"
            )
        else:
            raise NotImplemented()

        lava_dispatcher_host.docker_worker.run("2020.07.2.0010.g12371263", options)
        if platform.machine() == "x86_64":
            get_image.assert_called_with(
                "hub.lavasoftware.org/lava/lava/amd64/lava-dispatcher:2020.07.2.0010.g12371263"
            )
        elif platform.machine() == "aarch64":
            get_image.assert_called_with(
                "hub.lavasoftware.org/lava/lava/aarch64/lava-dispatcher:2020.07.2.0010.g12371263"
            )
        else:
            raise NotImplemented()
