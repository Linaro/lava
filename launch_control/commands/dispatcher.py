"""
Module with LaunchControlDispatcher - the command dispatcher
"""

import argparse

from .interface import Command

class LaunchControlDispatcher(object):
    """
    Class implementing command line interface for launch control
    """

    def __init__(self):
        self.parser = argparse.ArgumentParser(
                description="""
                Command line tool for interacting with Launch Control
                """,
                epilog="""
                Please report all bugs using the Launchpad bug tracker:
                http://bugs.launchpad.net/launch-control/+filebug
                """,
                add_help=False)
        self.subparsers = self.parser.add_subparsers(title="Sub-command to invoke")
        for command_cls in Command.get_subclasses():
            sub_parser = self.subparsers.add_parser(
                    command_cls.get_name(),
                    help=command_cls.get_help())
            sub_parser.set_defaults(command_cls=command_cls)
            command_cls.register_arguments(sub_parser)

    def dispatch(self, args=None):
        args = self.parser.parse_args(args)
        command = args.command_cls(self.parser, args)
        command.invoke()
        
def main():
    LaunchControlDispatcher().dispatch()

