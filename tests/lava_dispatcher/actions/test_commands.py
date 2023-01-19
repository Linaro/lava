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
                "hard_reset": "/path/to/hard-reset",
                "power_off": ["something", "something-else"],
                "users": {"do_something": {"do": "/bin/do", "undo": "/bin/undo"}},
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


@pytest.fixture
def hard_reset(action):
    action.parameters = {"name": "hard_reset"}
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


def test_builtin_command_run(hard_reset):
    hard_reset.run(None, 600)
    hard_reset.run_cmd.assert_called_with("/path/to/hard-reset")


def test_builtin_command_cleanup_is_noop(hard_reset):
    hard_reset.run(None, 600)
    hard_reset.run_cmd.reset_mock()
    hard_reset.cleanup(None)
    hard_reset.run_cmd.assert_not_called()


def test_builtin_command_not_defined_for_device(action):
    action.parameters = {"name": "pre_power_command"}
    assert not action.validate()  # should not crash


def test_multiple_commands(action, mocker):
    call = mocker.call
    action.parameters = {"name": "power_off"}
    action.validate()
    action.run(None, 600)
    action.run_cmd.assert_has_calls([call("something"), call("something-else")])
