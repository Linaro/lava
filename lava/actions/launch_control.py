#!/usr/bin/python
from lava.actions import BaseAction
from lava.config import LAVA_RESULT_DIR, MASTER_STR
import xmlrpclib
import re
import os

class cmd_submit_results(BaseAction):
    def run(self, server, stream, pathname):
        client = self.client
        try:
            self.in_master_shell()
        except:
            client.boot_master_image()

        client.run_shell_command(
            'mkdir -p /mnt/root', response = MASTER_STR)
        client.run_shell_command(
            'mount /dev/disk/by-label/testrootfs /mnt/root',
            response = MASTER_STR)
        client.run_shell_command(
            'mkdir -p %s' % LAVA_RESULT_DIR, response = MASTER_STR)
        client.run_shell_command(
            'cp /mnt/root/%s/*.bundle %s' % (LAVA_RESULT_DIR, LAVA_RESULT_DIR),
            response = MASTER_STR)
        # fix me: upload bundle files to server

        #Create l-c server connection
        dashboard_url = "%s/launch-control" % server
        xmlrpc_url = "%s/launch-control/xml-rpc/" % server

        srv = xmlrpclib.ServerProxy(xmlrpc_url, 
                allow_none=True, use_datetime=True)
 
        #fix me: get serial log

        #.bundle file pattern
        pattern = re.compile(".*\.bundle")
        filelist = os.listdir("%s" % LAVA_RESULT_DIR)
        for file in filelist:
            found = re.match(pattern, file)
            if found:
                filename = "%s/%s" % (LAVA_RESULT_DIR, file)

                f = open(filename, "rb")
                content = f.read()
                f.close()

                #fix me: attach serial log

                srv.put(content, filename, pathname)
