#!/usr/bin/python
from glob import glob
import imp
import os

class BaseAction(object):
    def __init__(self, context):
        self.context = context

    def get_client(self):
        return self.context.get_client()


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
