from lava_dispatcher.pipeline import *
from lava_dispatcher.utils import logging_spawn


class ConnectToSerial(Action):

    def run(self, connection, args=None):
        telnet = spawn_command(self.device.config.connection_command)
        return Connection(self.device, telnet)
