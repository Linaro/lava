import jinja2
import pathlib
import pytest

from lava_scheduler_app import environment


@pytest.fixture(autouse=True)
def update_settings(settings, monkeypatch):
    base = pathlib.Path(__file__).parent.parent.parent
    settings.DEVICES_PATH = str(base / "lava_scheduler_app" / "tests" / "devices")
    settings.DEVICE_TYPES_PATH = str(
        base / "etc" / "dispatcher-config" / "device-types"
    )
    settings.HEALTH_CHECKS_PATH = str(
        base / "lava_scheduler_app" / "tests" / "health-checks"
    )

    def devices():
        return jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                [settings.DEVICES_PATH, settings.DEVICE_TYPES_PATH]
            ),
            autoescape=False,
            trim_blocks=True,
        )

    def device_types():
        return jinja2.Environment(
            loader=jinja2.FileSystemLoader([settings.DEVICE_TYPES_PATH]),
            autoescape=False,
            trim_blocks=True,
        )

    monkeypatch.setattr(environment, "devices", devices)
    monkeypatch.setattr(environment, "device_types", device_types)
