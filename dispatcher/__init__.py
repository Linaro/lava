#!/usr/bin/python
from actions import get_all_cmds

def run_job(jobdata):
    lava_commands = get_all_cmds()

    target = jobdata['target']
    for cmd in jobdata['actions']:
        params = cmd.get('parameters', {})
        step = lava_commands[cmd['command']](target)
        step.run(**params)
