from .interface import Command
from launch_control import get_version

class help(Command):
    """
    Show a summary of all available commands
    """
    def invoke(self):
        self.parser.print_help()


class version(Command):
    """
    Show dashboard client version
    """
    def invoke(self):
        print "Dashboard client version: {version}".format(
                version = get_version())
