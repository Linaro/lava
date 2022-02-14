import argparse
import platform
import pytest
import lava_dispatcher_host.docker_worker


@pytest.fixture
def get_image(mocker):
    return mocker.patch("lava_dispatcher_host.docker_worker.get_image")


@pytest.fixture
def check_call(mocker):
    return mocker.patch("lava_dispatcher_host.docker_worker.subprocess.check_call")


@pytest.fixture
def Popen(mocker):
    return mocker.patch("lava_dispatcher_host.docker_worker.subprocess.Popen")


@pytest.fixture
def options(tmp_path):
    o = argparse.Namespace()
    o.worker_dir = tmp_path / "worker"
    o.build_dir = tmp_path / "build"
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


class TestBuildImage:
    def test_missing_dockerfile(self, tmp_path, check_call, mocker):
        image = "lavasoftware/lava-dispatcher:2021.08"
        build_dir = tmp_path / "build"
        build_dir.mkdir()

        lava_dispatcher_host.docker_worker.build_customized_image(image, build_dir)
        check_call.assert_not_called()

    def test_build_customized_image(self, tmp_path, check_call, mocker):
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

        check_call.assert_called_with(
            ["docker", "build", "--force-rm", "-f", "Dockerfile.lava", "-t", tag, "."],
            cwd=build_dir,
        )


class TestRun:
    def test_get_image_released(self, get_image, Popen, options):
        lava_dispatcher_host.docker_worker.run("2020.07", options)
        get_image.assert_called_with("lavasoftware/lava-dispatcher:2020.07")
        lava_dispatcher_host.docker_worker.run("2020.07.1", options)
        get_image.assert_called_with("lavasoftware/lava-dispatcher:2020.07.1")

    def test_get_image_development(self, get_image, Popen, options):
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
