from .interface import Command

class help(Command):
    """
    Show a summary of all available commands
    """
    def __init__(self, parser, args):
        self.parser = parser

    def invoke(self, args):
        self.parser.print_help()
