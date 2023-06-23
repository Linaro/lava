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
    o.sentry_dsn = None
    o.level = "INFO"

    return o


@pytest.fixture(scope="class")
def docker_image():
    class DockerImage:
        def __init__(self):
            self.name = "lavasoftware/lava-dispatcher:2023.01"
            # shell cmd to get worker option namespace.
            self.sh_cmd = [
                "docker",
                "run",
                "--rm",
                self.name,
                "python3",
                "-c",
                "from lava_common.worker import get_parser; print(get_parser().parse_args(['--url', 'dummy-url']))",
            ]
            self.option_ns = b"""
                Namespace(name='worker', debug=False,exit_on_version_mismatch=False,
                wait_jobs=False, worker_dir=PosixPath('/var/lib/lava/dispatcher/worker'),
                url='dummy-url', ws_url=None,http_timeout=600, ping_interval=20,
                job_log_interval=5, username=None, token=None, token_file=None,
                log_file='/var/log/lava-dispatcher/lava-worker.log', level='INFO')
            """
            self.available_options = [
                "name",
                "debug",
                "exit_on_version_mismatch",
                "wait_jobs",
                "worker_dir",
                "url",
                "ws_url",
                "http_timeout",
                "ping_interval",
                "job_log_interval",
                "username",
                "token",
                "token_file",
                "log_file",
                "level",
            ]

    return DockerImage()


@pytest.fixture
def get_options(mocker, docker_image):
    return mocker.patch(
        "lava_dispatcher_host.docker_worker.get_options",
        return_value=docker_image.available_options,
    )


class TestGetImage:
    def test_image_exists(self, check_output, mocker):
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
        popen = mocker.patch("lava_dispatcher_host.docker_worker.subprocess.Popen")
        popen().communicate.return_value = (None, None)
        popen().returncode = 0
        original_image = "lavasoftware/lava-dispatcher:2021.05"
        image = "lavasoftware/lava-dispatcher:2021.08"
        tag = f"{image}.customized"

        build_dir = tmp_path / "build"
        build_dir.mkdir()
        dockerfile = build_dir / "Dockerfile"
        dockerfile.write_text(f"{original_image}\nRUN echo test > /test")

        # 1. Test build without cache.
        lava_dispatcher_host.docker_worker.build_customized_image(image, build_dir)
        dockerfile_lava = build_dir / "Dockerfile.lava"
        assert dockerfile_lava.exists()
        content = dockerfile_lava.read_text()
        assert f"FROM {image}" in content
        assert f"FROM {original_image}" not in content

        popen.assert_called_with(
            [
                "docker",
                "build",
                "--force-rm",
                "-f",
                "Dockerfile.lava",
                "-t",
                tag,
                "--no-cache",
                ".",
            ],
            cwd=build_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        # 2. Test build using cache.
        lava_dispatcher_host.docker_worker.build_customized_image(
            image, build_dir, use_cache=True
        )
        popen.assert_called_with(
            [
                "docker",
                "build",
                "--force-rm",
                "-f",
                "Dockerfile.lava",
                "-t",
                tag,
                ".",
            ],
            cwd=build_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        # 3. Test build failure => SystemExit
        popen().returncode = 100
        with pytest.raises(SystemExit) as exc:
            lava_dispatcher_host.docker_worker.build_customized_image(image, build_dir)
        assert exc.value.code == 100


class TestRun:
    def test_get_image_released(self, get_image, Popen, options, mocker):
        mocker.patch("time.sleep")
        mocker.patch("lava_dispatcher_host.docker_worker.filter_options")
        lava_dispatcher_host.docker_worker.run("2020.07", options)
        get_image.assert_called_with("lavasoftware/lava-dispatcher:2020.07")
        lava_dispatcher_host.docker_worker.run("2020.07.1", options)
        get_image.assert_called_with("lavasoftware/lava-dispatcher:2020.07.1")

    def test_get_image_development(self, get_image, Popen, options, mocker):
        if platform.machine() == "x86_64":
            arch = "amd64"
        elif platform.machine() == "aarch64":
            arch = "aarch64"
        else:
            raise NotImplemented()
        mocker.patch("time.sleep")
        mocker.patch("lava_dispatcher_host.docker_worker.filter_options")
        has_image = mocker.patch(
            "lava_dispatcher_host.docker_worker.has_image", return_value=False
        )
        lava_dispatcher_host.docker_worker.run("2020.07.0010.g12371263", options)
        get_image.assert_called_with(
            f"hub.lavasoftware.org/lava/lava/{arch}/lava-dispatcher:2020.07.0010.g12371263"
        )
        has_image.assert_called_with(
            f"registry.gitlab.com/lava/lava/{arch}/lava-dispatcher:2020.07.0010.g12371263",
            manifest=True,
        )

        lava_dispatcher_host.docker_worker.run("2020.07.2.0010.g12371263", options)
        get_image.assert_called_with(
            f"hub.lavasoftware.org/lava/lava/{arch}/lava-dispatcher:2020.07.2.0010.g12371263"
        )
        has_image.assert_called_with(
            f"registry.gitlab.com/lava/lava/{arch}/lava-dispatcher:2020.07.2.0010.g12371263",
            manifest=True,
        )


class TestOptions:
    def test_get_options_call(self, check_output, mocker, docker_image):
        mocker.patch("re.findall")
        lava_dispatcher_host.docker_worker.get_options(docker_image.name)
        check_output.assert_called_with(
            docker_image.sh_cmd,
            stderr=subprocess.DEVNULL,
        )

    def test_get_options_parsing(self, mocker, docker_image):
        mocker.patch(
            "lava_dispatcher_host.docker_worker.subprocess.check_output",
            return_value=docker_image.option_ns,
        )
        options = lava_dispatcher_host.docker_worker.get_options(docker_image.name)
        assert options == docker_image.available_options

    def test_filter_options_available(self, options, docker_image, get_options):
        ret = lava_dispatcher_host.docker_worker.filter_options(
            options, docker_image.name
        )
        get_options.assert_called_with(docker_image.name)
        assert "--level" in ret

    def test_filter_options_unavailable(self, options, docker_image, get_options):
        ret = lava_dispatcher_host.docker_worker.filter_options(
            options, docker_image.name
        )
        get_options.assert_called_with(docker_image.name)
        assert "--sentry-dsn" not in ret
