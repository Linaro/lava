# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Interface for all launch-control-tool commands
"""

import inspect

from launch_control.utils.registry import RegistryBase


class Command(RegistryBase):
    """
    Base class for all command line tool sub-commands.
    """

    def __init__(self, parser, args):
        """
        Prepare instance for executing commands.

        This method is called immediately after all arguments are parsed
        and results are available. This gives subclasses a chance to
        configure themselves.

        The default implementation stores both arguments
        """
        self.parser = parser
        self.args = args

    def invoke(self):
        """
        Invoke command action.
        """
        raise NotImplementedError()

    @classmethod
    def get_name(cls):
        """
        Return the name of this command.

        The default implementation strips any leading underscores
        and replaces all other underscores with dashes.
        """
        return cls.__name__.lstrip("_").replace("_", "-")

    @classmethod
    def get_help(cls):
        """
        Return the help message of this command
        """
        return inspect.getdoc(cls)

    @classmethod
    def register_arguments(cls, parser):
        """
        Register arguments if required.

        Subclasses can override this to add any arguments that will be
        exposed to the command line interface.
        """
        pass
