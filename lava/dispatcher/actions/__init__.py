#!/usr/bin/python
from glob import glob
import imp
from lava.dispatcher.client import LavaClient
from lava.dispatcher.android_client import LavaAndroidClient
import os

class BaseAction(object):
    def __init__(self, context):
        self.context = context

    @property
    def client(self):
        return self.context.client


class BaseAndroidAction(BaseAction):
    network_interface = "eth0"

    def __init__(self, client):
        self.client = LavaAndroidClient(client)

    def check_sys_bootup(self):
        result_pattern = "([0-1])"
        cmd = "getprop sys.boot_completed"
        self.client.proc.sendline(cmd)
        id = self.client.proc.expect([result_pattern], timeout = 60)
        if id == 0:
            return True
        else:
            return False

def _find_commands(module):
    cmds = {}
    for name, cls in module.__dict__.iteritems():
        if name.startswith("cmd_"):
            real_name = name[4:]
            cmds[real_name] = cls
    return cmds

def get_all_cmds():
    cmds = {}
    cmd_path = os.path.dirname(os.path.realpath(__file__))
    for f in glob(os.path.join(cmd_path,"*.py")):
        module = imp.load_source("module", os.path.join(cmd_path,f))
        cmds.update(_find_commands(module))
    return cmds
