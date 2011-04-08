#!/usr/bin/python
from lava.dispatcher.actions import BaseAction

class cmd_submit_results(BaseAction):
    def run(self, server, stream):
        print "submit_results"
