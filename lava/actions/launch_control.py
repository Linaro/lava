#!/usr/bin/python
from lava.actions import BaseAction
from xmlrpclib import ServerProxy
import sys

class cmd_submit_results(BaseAction):
    def run(self, server, stream):
        srv = ServerProxy("%s:8000/xml-rpc/" % server)

if __name__ == "__main__":
    srv = ServerProxy("http://localhost:8000/xml-rpc/")
    print srv.version()
    with open(sys.argv[1]) as fd:
        jn = fd.read()
    try:
        srv.put(jn, "abrek.json", "tests")
    except:
        print "error"
        raise
