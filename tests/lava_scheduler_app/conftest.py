import pathlib

import pytest


@pytest.fixture(autouse=True)
def update_settings(settings, mocker, tmp_path):
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
            "dispatcher": [
                "/etc/lava-server/dispatcher.d/{name}/dispatcher.yaml",
                "/etc/lava-server/dispatcher.d/{name}.yaml",
            ],
            "env": [
                "/etc/lava-server/dispatcher.d/{name}/env.yaml",
                "/etc/lava-server/env.yaml",
            ],
            "env-dut": [
                "/etc/lava-server/dispatcher.d/{name}/env-dut.yaml",
                "/etc/lava-server/env-dut.yaml",
            ],
            "health-check": ([settings.HEALTH_CHECKS_PATH], "{name}.yaml"),
        },
    )

    mocker.patch(
        "lava_scheduler_app.models.TestJob.output_dir", str(tmp_path / "job-output")
    )
