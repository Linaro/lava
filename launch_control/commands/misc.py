from .interface import Command

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
        from launch_control import __version__ as client_version
        print "Dashboard client version: {version}".format(
                version = ".".join(map(str, client_version)))
