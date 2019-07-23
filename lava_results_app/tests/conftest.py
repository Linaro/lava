import pathlib
import pytest


@pytest.fixture(autouse=True)
def update_settings(settings):
    base = pathlib.Path(__file__).parent.parent.parent
    settings.DEVICES_PATH = str(base / "lava_scheduler_app" / "tests" / "devices")
    settings.DEVICE_TYPES_PATH = str(
        base / "etc" / "dispatcher-config" / "device-types"
    )
    settings.HEALTH_CHECKS_PATH = str(
        base / "lava_scheduler_app" / "tests" / "health-checks"
    )
