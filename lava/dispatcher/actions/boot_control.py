#!/usr/bin/python
from lava.dispatcher.actions import BaseAction

class cmd_boot_linaro_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        client = self.client
        #Workaround for commands coming too quickly at this point
        client.proc.sendline("")
        status = 'pass'
        try:
            client.boot_linaro_image()
        except:
            status = 'fail'
            raise
        finally:
            self.context.test_data.add_result("boot_image", status)

class cmd_boot_master_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        client = self.client
        client.boot_master_image()
