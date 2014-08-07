from lava_dispatcher.pipeline import *
from lava_dispatcher.client.base import CommandRunner


class ShellSession(Connection):

    def __init__(self, device, raw_connection):
        super(ShellSession, self).__init__(device, raw_connection)
        self.__runner__ = None

    @property
    def runner(self):
        if self.__runner__ is None:
            device = self.device
            connection = self.raw_connection
            prompt_str = device.config.test_image_prompts
            prompt_str_includes_rc = device.config.tester_ps1_includes_rc
            self.__runner__ = CommandRunner(connection, prompt_str,
                                            prompt_str_includes_rc)
        return self.__runner__

    def run_command(self, command):
        self.runner.run(command)

    def wait(self):
        self.raw_connection.sendline("")
        self.runner.wait_for_prompt()


class ExpectShellSession(Action):

    def run(self, connection):
        shell = ShellSession(connection.device, connection.raw_connection)
        shell.wait()
        return shell
