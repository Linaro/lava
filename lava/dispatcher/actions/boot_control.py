#!/usr/bin/python
from lava.dispatcher.actions import BaseAction, BaseAndroidAction

class cmd_boot_linaro_android_image(BaseAndroidAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        #Workaround for commands coming too quickly at this point
        client = self.client
        client.proc.sendline("")
        client.boot_linaro_android_image()

class cmd_boot_linaro_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        client = self.client
        #Workaround for commands coming too quickly at this point
        client.proc.sendline("")
        client.boot_linaro_image()

class cmd_boot_master_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        client = self.client
        client.boot_master_image()
