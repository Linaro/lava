from lava_dispatcher.pipeline import *


class ConnectViaSSH(Action):

    def run(self, connection):
        ssh = spawn_command('ssh -o Compression=yes -o UserKnownHostsFile=/dev/null -o PasswordAuthentication=no -o StrictHostKeyChecking=no -o LogLevel=FATAL -l root 192.168.1.100')  # FIXME
        return Connection(self.device, ssh)
