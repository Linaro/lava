#!/usr/bin/python
from lava.dispatcher.actions import BaseAction

class cmd_boot_linaro_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        client = self.get_client()
        #Workaround for commands coming too quickly at this point
        client.proc.sendline("")
        client.boot_linaro_image()

class cmd_boot_master_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        client = self.get_client()
        client.boot_master_image()
