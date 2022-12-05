import pathlib

import pytest
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

from lava_server.files import File


@pytest.fixture(autouse=True)
def update_settings(settings, mocker):
    base = pathlib.Path(__file__).parent.parent.parent
    settings.DEVICES_PATH = str(base / "tests" / "lava_scheduler_app" / "devices")
    settings.DEVICE_TYPES_PATHS = [
        str(base / "etc" / "dispatcher-config" / "device-types")
    ]
    settings.HEALTH_CHECKS_PATH = str(
        base / "tests" / "lava_scheduler_app" / "health-checks"
    )
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "device": ([settings.DEVICES_PATH], "{name}.jinja2"),
            "device-type": (settings.DEVICE_TYPES_PATHS, "{name}.jinja2"),
            "health-check": ([settings.HEALTH_CHECKS_PATH], "{name}.yaml"),
        },
    )

    def devices():
        return JinjaSandboxEnv(
            loader=File("device").loader(), autoescape=False, trim_blocks=True
        )

    def device_types():
        return JinjaSandboxEnv(
            loader=File("device-type").loader(), autoescape=False, trim_blocks=True
        )

    mocker.patch("lava_scheduler_app.environment.devices", devices)
    mocker.patch("lava_scheduler_app.environment.device_types", device_types)
