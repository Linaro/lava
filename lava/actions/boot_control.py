#!/usr/bin/python
from lava.actions import BaseAction

class cmd_boot_linaro_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        self.client.boot_linaro_image()

class cmd_boot_master_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        self.client.boot_master_image()
