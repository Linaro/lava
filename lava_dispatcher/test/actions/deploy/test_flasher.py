import pytest
import select
import subprocess

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.deploy.flasher import Flasher, FlasherAction
from lava_dispatcher.device import PipelineDevice
from lava_dispatcher.job import Job

# This will be monkey patched
import lava_dispatcher.utils.shell
import lava_dispatcher.actions.deploy.docker


def test_run(monkeypatch):
    class FD:
        def readlines(self):
            return []

    class Proc:
        def __init__(self):
            self.stderr = FD()
            self.stdout = FD()

        def poll(self):
            return 0

        def wait(self):
            return 0

    class Poller:
        def register(self, fd, flag):
            pass

    commands = [
        ["nice", "/home/lava/bin/PiCtrl.py", "PowerPlug", "0", "off"],
        ["nice", "touch"],
    ]

    def Popen(cmd, cwd, stdout, stderr, bufsize, universal_newlines):
        assert cmd == commands.pop(0)
        assert stdout == subprocess.PIPE
        assert stderr == subprocess.PIPE
        assert bufsize == 1
        assert universal_newlines
        return Proc()

    monkeypatch.setattr(subprocess, "Popen", Popen)
    monkeypatch.setattr(select, "epoll", lambda: Poller())

    action = FlasherAction()
    device = PipelineDevice(
        {
            "actions": {
                "deploy": {
                    "methods": {
                        "flasher": {"commands": ["{HARD_RESET_COMMAND}", "touch"]}
                    }
                }
            },
            "commands": {"hard_reset": "/home/lava/bin/PiCtrl.py PowerPlug 0 off"},
        }
    )
    action.job = Job(1234, {}, None)
    action.job.device = device
    action.parameters = {"namespace": "common", "images": {}}
    action.section = Flasher.action_type

    # self.commands is populated by validate
    action.validate()
    assert action.errors == []

    # Run the action
    action.run(None, 10)
    assert commands == []


def test_accepts():
    pipe = Pipeline(job=Job(1234, {}, None))
    pipe.add_action = lambda a, b: None
    flasher = Flasher(pipe, {})

    # Normal case
    device = {"actions": {"deploy": {"methods": "flasher"}}}
    params = {"to": "flasher"}
    assert flasher.accepts(device, params) == (True, "accepted")

    # Flasher is not defined
    device = {"actions": {"deploy": {"methods": "tftp"}}}
    params = {"to": "flasher"}
    assert flasher.accepts(device, params) == (
        False,
        "'flasher' not in the device configuration deploy methods",
    )

    # Flasher is not requested
    device = {"actions": {"deploy": {"methods": "flasher"}}}
    params = {"to": "tftp"}
    assert flasher.accepts(device, params) == (False, '"to" parameter is not "flasher"')
