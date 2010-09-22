# Copyright (c) 2010 Linaro
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Module with LaunchControlDispatcher - the command dispatcher
"""

import argparse
import sys

from launch_control.commands.interface import Command


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
        self.subparsers = self.parser.add_subparsers(
                title="Sub-command to invoke")
        for command_cls in Command.get_subclasses():
            if getattr(command_cls, '__abstract__', False):
                continue
            sub_parser = self.subparsers.add_parser(
                    command_cls.get_name(),
                    help=command_cls.get_help())
            sub_parser.set_defaults(command_cls=command_cls)
            command_cls.register_arguments(sub_parser)

    def dispatch(self, args=None):
        args = self.parser.parse_args(args)
        command = args.command_cls(self.parser, args)
        return command.invoke()


def main():
    sys.exit(LaunchControlDispatcher().dispatch())

