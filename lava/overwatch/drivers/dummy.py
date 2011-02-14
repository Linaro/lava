from lava.overwatch.drivers import BaseOverwatchDriver


class DummyDriver(BaseOverwatchDriver):
    """
    Dummy overwatch driver
    """

    INTERFACES = {}

    def _get_interfaces(self):
        return self.INTERFACES
