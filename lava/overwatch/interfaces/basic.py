"""
Interfaces for basic test activities
"""

from lava.overwatch.decorators import action
from lava.overwatch.interfaces import IOverwatchDriverInterface


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
    def prepare_or_refresh_test(self, test_name):
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
