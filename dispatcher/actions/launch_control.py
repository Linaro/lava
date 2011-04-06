#!/usr/bin/python
from dispatcher.actions import BaseAction
from dispatcher.config import LAVA_RESULT_DIR, MASTER_STR, CONMUX_LOG_DIR
import xmlrpclib
import re
import os
import shutil
import socket
from threading import Thread

class cmd_submit_results(BaseAction):
    def run(self, server, stream, pathname):
        """
        stream doesn't use here, all bundles in LAVA_RESULT_DIR will upload to
        dashboard
        The run function is somewhat a bit longer
        """
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
        client.run_shell_command('umount /mnt/root', response = MASTER_STR)

        #Clean up LAVA result directory, here, assume LAVA result dir path is
        # same as master image on server
        shutil.rmtree("%s" % LAVA_RESULT_DIR)
        os.mkdir("%s" % LAVA_RESULT_DIR)

        #Upload bundle list-bundle.lst
        client.run_shell_command('cd %s' % LAVA_RESULT_DIR,
            response = MASTER_STR)
        client.run_shell_command('ls *.bundle > bundle.lst',
            response = MASTER_STR)

        t = SimpleHTTPServer("bundle.lst")
        t.start()
        client.run_shell_command(
            'cat bundle.lst |nc %s %d' % (LAVA_SERVER_IP, t.get_port()),
            response = MASTER_STR)
        t.join()

        f = open("%s/bundle.lst" % LAVA_RESULT_DIR, "rb")
        bundle_list = f.read()
        f.close()

        #Upload bundle files to server
        for bundle in bundle_list:
            t = SimpleHTTPServer("%s/%s", LAVA_RESULT_DIR, bundle)
            t.start()
            client.run_shell_command(
                'cat %s/%s | nc %s %s' % (LAVA_RESULT_DIR, bundle, 
                    LAVA_SERVER_IP, t.get_port()),
                response = MASTER_STR)
            t.join()

        #Create l-c server connection
        dashboard_url = "%s/launch-control" % server
        xmlrpc_url = "%s/launch-control/xml-rpc/" % server
        srv = xmlrpclib.ServerProxy(xmlrpc_url, 
                allow_none=True, use_datetime=True)
 
        #.bundle file pattern
        #bundle list can also come from bundle.lst
        pattern = re.compile(".*\.bundle")
        filelist = os.listdir("%s" % LAVA_RESULT_DIR)
        for file in filelist:
            found = re.match(pattern, file)
            if found:
                filename = "%s/%s" % (LAVA_RESULT_DIR, file)
                f = open(filename, "rb")
                content = f.read()
                f.close()
                srv.put(content, filename, pathname)

class SimpleHTTPServer(Thread):
    """
    Simple HTTP Server for uploading bundles
    """
    def __init__(self, filename):
        Thread.__init__(self)
        self.filename = filename
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(('', 0))

    def get_port(self):
        return self.s.getsockname()[1]

    def run(self):
        self.s.listen(1)
        conn, addr = self.s.accept()
        f = open(self.filename, 'w')
        while(1):
            #10KB per time
            data = conn.recv(10240)
            if not data: break
            f.write(data)
            print data
        f.close()
