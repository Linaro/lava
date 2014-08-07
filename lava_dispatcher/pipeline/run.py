from lava_dispatcher.pipeline import *


class RunShellAction(Action):

    def run(self, connection):
        connection.run_command("date")  # FIXME read command from parameters
        return connection
