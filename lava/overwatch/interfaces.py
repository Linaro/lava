"""
Interfaces for pluggable components of the stack.
"""


from lava.overwatch.decorators import action


class IOverwatchDriver(object):
    """
    Overwatch drivers are responsible for "wrapping" all the logic required to
    manage physical devices connected to the LAVA environment. Since it's
    impossible to predict all theoretical use-cases that this stack can
    participate in the design is modeled around pluggable interfaces.

    A driver can advertise all the implemented interfaces via the
    enumerate_interfaces() method. Any service that wants to use a particular
    interface can call get_interface() with the name of the required
    functionality.

    By convention all interfaces designed by the LAVA team will use the
    ``lava.*`` namespace.  Other namespaces are available to experiments,
    extensions and proprietary subsystems.

    In practice we expect some common functionality from overwatch drivers to
    be able to use them in our test environment in the way that we currently
    designed the system to support (for typical linux distributions built for
    ARM).
    """

    def __init__(self, config):
        """
        Initialize the driver with the specified configuration string.
        """
    
    def enumerate_interfaces(self):
        """
        Enumerate interfaces supported and implemented by this overwatch driver
        """

    def get_interface(self, name):
        """
        Construct an instance of the interface with the requested name.

        Raises ValueError if the name does not designate an interface
        implemented by this driver 
        """


class IOverwatchDriverInterface(object):

    def get_name(self):
        """
        Return the canonical name of the interface
        """

    def enumerate_actions(self):
        """
        Enumerate actions supported and implemented by this interface
        """

    def run_action(self, name, params):
        """
        Invoke public action with the specified parameters
        """


class IShellControl(IOverwatchDriverInterface):
    """
    Well known interface to start shell commands on a device.  Can be used
    directly if needed. Otherwise is most useful as a means to implement higher
    level interfaces.

    The shell commands here are not specified but an UNIX-like environment may
    be assumed. 
    """

    INTERFACE_NAME = "lava.ShellControl"

    @action
    def invoke_shell_command(self, *args, **kwargs):
        """
        Invoke shell command, arguments are identical to subprocess.Popen()
        call.
        """


class ITestControl(IOverwatchDriverInterface):
    """
    Well known interface to start tests. The interface is purposefully
    unspecific to be compatible with both abrek and other frameworks that may
    be used in its place. 
    """

    INTERFACE_NAME = "lava.TestControl"

    @action
    def prepate_or_refresh_test(self, test_name):
        """
        Refresh or install test with the given name.

        Some tests are not static, that is, they may be rebuild from source
        with the local compiler. Other tests will ignore this request and
        simply install themselves if missing.
        """

    @action
    def run_test(self, name, params):
        """
        Run test with the specified parameters.

        The parameters must be an array on strings. The test may be a
        standalone program, a library linked to the image or something entirely
        different. Therefore the interface is as simple as possible.

        The test must interact with the test monitoring any recording system
        (that is, it must be able to produce results in the agreed upon
        format).
        """


class IDashboardControl(IOverwatchDriverInterface):
    """
    Well known interface for interacting with the dashboard
    """

    INTERFACE_NAME = "lava.DashboardControl"

    @action
    def push_results_to(self, dashboard_url, pathname):
        """
        Push all the result gathered during job processing to the bundle stream
        in a dashboard at the specified URL.
        """
