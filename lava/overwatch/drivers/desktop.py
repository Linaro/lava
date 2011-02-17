from lava.overwatch.drivers import BaseOverwatchDriver
from lava.overwatch.interfaces import IShellControl
import subprocess


class DesktopDriver(BaseOverwatchDriver):
    """
    Driver for accessing typical desktop computers over SSH
    """

    def _get_interfaces(self):
        return {
            IShellControl.INTERFACE_NAME: lambda self: SSHShellControl(**self._config.get("ssh", {}))
        }


class SSHShellControl(IShellControl):

    def __init__(self, hostname, user=None, port=None):
        self.hostname = hostname
        self.user = user
        self.port = port

    def _construct_ssh_cmd(self):
        cmd = ['ssh']
        if self.port is not None:
            cmd.extend(['-p', "%d" % self.port])
        if self.user is None:
            cmd.append(self.hostname)
        else:
            cmd.append("%s@%s" % (self.user, self.hostname))
        return cmd

    def invoke_shell_command(self, *args, **kwargs):
        if len(args) == 0:
            raise ValueError("At least one argument must be specified")
        cmd = self._construct_ssh_cmd()
        cmd.extend(args[0])
        return subprocess.call(cmd, *args[1:], **kwargs)
