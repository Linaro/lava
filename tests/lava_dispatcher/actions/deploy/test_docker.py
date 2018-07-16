import pytest
import subprocess

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.deploy.docker import Docker, DockerAction
from lava_dispatcher.job import Job

# This will be monkey patched
import lava_dispatcher.utils.shell
import lava_dispatcher.actions.deploy.docker


def test_validate(monkeypatch):
    check_output_args = [
        ["docker", "version", "-f", "{{.Server.Version}}"],
        ["docker", "version", "-f", "{{.Client.Version}}"],
    ]

    def check_output(args):
        assert args == check_output_args[0]
        check_output_args.pop(0)
        return b"18.03.1-ce"

    monkeypatch.setattr(
        lava_dispatcher.actions.deploy.docker, "which", lambda a: "/usr/bin/docker"
    )
    monkeypatch.setattr(subprocess, "check_output", check_output)

    action = DockerAction()
    action.job = Job(1234, {}, None)
    action.job.device = {
        "actions": {"deploy": {"methods": {"docker": {"options": {"remote": None}}}}}
    }
    action.parameters = {"namespace": "common", "image": "debian:9"}
    action.section = Docker.section
    action.validate()
    assert not action.errors
    assert (
        action.get_namespace_data(action=action.name, label="image", key="name")
        == "debian:9"
    )


def test_validate_wrong_image(monkeypatch):
    monkeypatch.setattr(
        lava_dispatcher.actions.deploy.docker, "which", lambda a: "/usr/bin/docker"
    )
    monkeypatch.setattr(subprocess, "check_output", lambda a: b"18.03.1-ce")

    action = DockerAction()
    action.job = Job(1234, {}, None)
    action.job.device = {
        "actions": {"deploy": {"methods": {"docker": {"options": {"remote": None}}}}}
    }
    action.parameters = {"namespace": "common", "image": "debian()"}
    action.section = Docker.section
    action.validate()
    assert action.errors == ["image name 'debian()' is invalid"]

    action = DockerAction()
    action.job = Job(1234, {}, None)
    action.job.device = {
        "actions": {"deploy": {"methods": {"docker": {"options": {"remote": None}}}}}
    }
    action.parameters = {"namespace": "common", "image": "debian hello"}
    action.section = Docker.section
    action.validate()
    assert action.errors == ["image name 'debian hello' is invalid"]


def test_validate_raise(monkeypatch):
    def check_output(args):
        raise subprocess.CalledProcessError(
            args,
            "Got permission denied while trying to connect to the Docker daemon socket",
        )

    monkeypatch.setattr(
        lava_dispatcher.actions.deploy.docker, "which", lambda a: "/usr/bin/docker"
    )
    monkeypatch.setattr(subprocess, "check_output", check_output)

    action = DockerAction()
    action.job = Job(1234, {}, None)
    action.job.device = {
        "actions": {"deploy": {"methods": {"docker": {"options": {"remote": None}}}}}
    }
    action.parameters = {"namespace": "common", "image": "debian:9"}
    action.section = Docker.section
    with pytest.raises(InfrastructureError) as exc:
        action.validate()
    assert exc.match(
        "Got permission denied while trying to connect to the Docker daemon socket"
    )
    assert not action.errors


def test_validate_raise_which(monkeypatch):
    def raise_infra(path):
        assert path == "docker"
        raise InfrastructureError("Cannot find command '%s' in $PATH" % path)

    monkeypatch.setattr(lava_dispatcher.actions.deploy.docker, "which", raise_infra)
    monkeypatch.setattr(subprocess, "check_output", lambda a: b"18.03.1-ce")

    action = DockerAction()
    action.job = Job(1234, {}, None)
    action.job.device = {
        "actions": {"deploy": {"methods": {"docker": {"options": {"remote": None}}}}}
    }
    action.parameters = {"namespace": "common", "image": "debian:9"}
    action.section = Docker.section
    with pytest.raises(InfrastructureError) as exc:
        action.validate()
    assert exc.match("Cannot find command 'docker' in \\$PATH")
    assert not action.errors


def test_run(monkeypatch):
    def check_run_cmd(command_list, allow_fail=False, error_msg=None, cmw=None):
        assert command_list == ["docker", "pull", "debian:9"]
        assert not allow_fail
        return """9: Pulling from library/debian
Digest: sha256:6ee341d1cf3da8e6ea059f8bc3af9940613c4287205cd71d7c6f9e1718fdcb9b
Status: Image is up to date for debian:9"""

    action = DockerAction()
    action.job = Job(1234, {}, None)
    action.parameters = {"namespace": "common", "image": "debian:9"}
    action.section = Docker.section
    action.run_cmd = check_run_cmd
    action.local = False
    action.image_name = "debian:9"
    action.run(None, 10)


def test_accepts(monkeypatch):
    monkeypatch.setattr(DockerAction, "test_needs_deployment", lambda a, b: False)
    monkeypatch.setattr(DockerAction, "test_needs_overlay", lambda a, b: False)

    pipe = Pipeline(job=Job(1234, {}, None))
    docker = Docker

    # Normal case
    device = {"actions": {"deploy": {"methods": "docker"}}}
    params = {"to": "docker", "image": "debian:buster"}
    assert docker.accepts(device, params) == (True, "accepted")

    # Docker is not defined
    device = {"actions": {"deploy": {"methods": "tftp"}}}
    params = {"to": "docker", "image": "debian:buster"}
    assert docker.accepts(device, params) == (
        False,
        "'docker' not in the device configuration deploy methods",
    )

    # Docker is not requested
    device = {"actions": {"deploy": {"methods": "docker"}}}
    params = {"to": "tftp"}
    assert docker.accepts(device, params) == (False, '"to" parameter is not "docker"')

    # image is missing
    device = {"actions": {"deploy": {"methods": "docker"}}}
    params = {"to": "docker"}
    assert docker.accepts(device, params) == (
        False,
        '"image" is not in the deployment parameters',
    )
