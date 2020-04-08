import pytest
from lava_common.timeout import Timeout
from lava_dispatcher.actions.commands import CommandAction
from lava_dispatcher.device import PipelineDevice
from lava_dispatcher.job import Job


@pytest.fixture
def device():
    return PipelineDevice(
        {
            "commands": {
                "users": {"do_something": {"do": "/bin/do", "undo": "/bin/undo"}}
            }
        }
    )


@pytest.fixture
def action(device, mocker):
    a = CommandAction()
    a.job = Job(42, {}, None)
    a.job.timeout = Timeout("job")
    a.job.device = device
    a.run_cmd = mocker.MagicMock()
    return a


@pytest.fixture()
def do_something(action):
    action.parameters = {"name": "do_something"}
    assert action.validate()
    return action


def test_run(do_something):
    do_something.run(None, 600)
    do_something.run_cmd.assert_called_with("/bin/do")


def test_cleanup(do_something):
    do_something.run(None, 600)
    do_something.cleanup(None)
    do_something.run_cmd.assert_called_with("/bin/undo")


def test_unknown_command(action):
    action.parameters = {"name": "unknown_command"}
    assert not action.validate()
    assert "Unknown user command 'unknown_command'" in action.errors


def test_unconfigured_device(action):
    action.job.device = PipelineDevice({})
    action.parameters = {"name": "some-action"}
    assert not action.validate()  # should not crash
