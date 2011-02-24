#!/usr/bin/python
from lava.actions import BaseAction

class cmd_test_abrek(BaseAction):
    def run(self, test_name):
        print "abrek run %s" % test_name
