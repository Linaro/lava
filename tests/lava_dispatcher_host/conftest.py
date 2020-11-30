import pytest


@pytest.fixture(autouse=True)
def pyudev(mocker):
    return mocker.patch("lava_dispatcher_host.pyudev")
