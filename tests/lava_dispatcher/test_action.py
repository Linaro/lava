import logging
import pytest
import subprocess

from lava_common.exceptions import LAVABug
from lava_dispatcher.action import Action
from lava_dispatcher.job import Job


def test_run_command(caplog, monkeypatch):
    def check_output(args, stderr=None, cwd=None):
        assert args == ["/bin/true", "--hello", "world"]
        assert stderr == subprocess.STDOUT
        assert cwd is None
        return "some line of text\nsome more!".encode("utf-8")

    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(subprocess, "check_output", check_output)
    a = Action()
    assert (
        a.run_command(["/bin/true", "--hello", "world"])
        == "some line of text\nsome more!"
    )
    assert caplog.record_tuples == [
        ("dispatcher", 10, "/bin/true --hello world"),
        ("dispatcher", 10, "output: some line of text"),
        ("dispatcher", 10, "output: some more!"),
    ]


def test_run_command_fail(caplog, monkeypatch):
    def check_output(args, stderr=None, cwd=None):
        assert args == ["/bin/true", "--hello", "world"]
        assert stderr == subprocess.STDOUT
        assert cwd is None
        raise subprocess.CalledProcessError(
            cmd=args, returncode=1, output="Unable to say 'hello'".encode("utf-8")
        )

    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(subprocess, "check_output", check_output)
    a = Action()
    a.name = "my-action"
    # 1/ allow_fail == False
    assert not a.run_command(["/bin/true", "--hello", "world"])
    assert caplog.record_tuples == [
        ("dispatcher", 10, "/bin/true --hello world"),
        (
            "dispatcher",
            40,
            """action: my-action
command: ['/bin/true', '--hello', 'world']
message: Command '['/bin/true', '--hello', 'world']' returned non-zero exit status 1.
output: Unable to say 'hello'
""",
        ),
    ]

    assert a.errors == ["Unable to say 'hello'"]
    # 2/ allow_fail == True
    caplog.clear()
    assert a.run_command(["/bin/true", "--hello", "world"], allow_fail=True)
    assert caplog.record_tuples == [
        ("dispatcher", 10, "/bin/true --hello world"),
        (
            "dispatcher",
            20,
            """action: my-action
command: ['/bin/true', '--hello', 'world']
message: Command '['/bin/true', '--hello', 'world']' returned non-zero exit status 1.
output: Unable to say 'hello'
""",
        ),
        ("dispatcher", 10, "output: Unable to say 'hello'"),
    ]


def test_run_command_not_list():
    a = Action()
    with pytest.raises(LAVABug) as exc:
        a.run_command("/bin/true")
    assert exc.match("commands to run_command need to be a list")


def test_namespace_data():
    a = Action()
    a.parameters = {"namespace": "common"}
    a.job = Job(1234, {}, None)

    # Grab a string
    assert a.get_namespace_data(action="download", label="kernel", key="url") is None
    a.set_namespace_data(action="download", label="kernel", key="url", value="hello")
    assert a.data == {"common": {"download": {"kernel": {"url": "hello"}}}}
    assert a.get_namespace_data(action="download", label="kernel", key="url") is "hello"

    # Grab a dictionary
    assert a.get_namespace_data(action="deploy", label="test", key="args") is None
    data = {"hello": "world"}
    a.set_namespace_data(action="deploy", label="test", key="args", value=data)
    assert a.get_namespace_data(action="deploy", label="test", key="args") is not data
    assert a.get_namespace_data(action="deploy", label="test", key="args") == data
    assert (
        a.get_namespace_data(action="deploy", label="test", key="args", deepcopy=False)
        is data
    )


def test_namespace_data_namespace():
    pass


def test_namespace_data_parameters():
    a = Action()
    a.job = Job(1234, {}, None)

    # Grab a string
    params = {"namespace": "common"}
    assert (
        a.get_namespace_data(
            action="download", label="kernel", key="url", parameters=params
        )
        is None
    )
    a.set_namespace_data(
        action="download", label="kernel", key="url", value="world", parameters=params
    )
    assert a.data == {"common": {"download": {"kernel": {"url": "world"}}}}
    assert (
        a.get_namespace_data(
            action="download", label="kernel", key="url", parameters=params
        )
        is "world"
    )

    params = {"namespace": "testing"}
    assert (
        a.get_namespace_data(
            action="download", label="kernel", key="url", parameters=params
        )
        is None
    )
    a.set_namespace_data(
        action="download", label="kernel", key="url", value="hello", parameters=params
    )
    assert a.data == {
        "common": {"download": {"kernel": {"url": "world"}}},
        "testing": {"download": {"kernel": {"url": "hello"}}},
    }
    assert (
        a.get_namespace_data(
            action="download", label="kernel", key="url", parameters=params
        )
        is "hello"
    )
