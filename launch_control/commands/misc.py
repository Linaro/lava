from .interface import Command

class help(Command):
    """
    Show a summary of all available commands
    """
    def invoke(self):
        self.parser.print_help()
