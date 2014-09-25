from lava_dispatcher.pipeline import Action
from lava_dispatcher.pipeline.connection import Connection


class ConnectViaSSH(Action):

    def run(self, connection, args=None):
        ssh = self._run_command(
            'ssh -o Compression=yes -o UserKnownHostsFile=/dev/null '
            '-o PasswordAuthentication=no -o StrictHostKeyChecking=no '
            '-o LogLevel=FATAL -l root 192.168.1.100')  # FIXME
        return Connection(self.job, ssh)
