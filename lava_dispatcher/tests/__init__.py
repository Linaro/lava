import logging

from lava_dispatcher.shell import ShellCommand
from lava_dispatcher.tests.utils import DummyLogger


logging.getLogger("requests").setLevel(logging.WARNING)


def shellcommand_dummy_logger_init(self, command, lava_timeout, logger=None, cwd=None):
    self.__old_init__(command, lava_timeout, DummyLogger(), cwd)


ShellCommand.__old_init__ = ShellCommand.__init__
ShellCommand.__init__ = shellcommand_dummy_logger_init
