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

        The default implementation does not do anything.
        """
        pass

    def invoke(self, args):
        """
        Invoke command action.
        """
        raise NotImplemented()

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

