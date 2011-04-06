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
        # same as master image on server, and use like LAVA_RESULT_DIR/panda01
        # rmtree may raise an error when using a board at first time
        server_result_dir = "%s/%s" % (LAVA_RESULT_DIR, client.hostname)
        shutil.rmtree(server_result_dir)
        os.mkdir(server_result_dir)

        #Upload bundle list-bundle.lst
        client.run_shell_command('cd %s' % server_result_dir,
            response = MASTER_STR)
        client.run_shell_command('ls *.bundle > bundle.lst',
            response = MASTER_STR)

        t = ResultUploader("bundle.lst")
        t.start()
        client.run_shell_command(
            'cat bundle.lst |nc %s %d' % (LAVA_SERVER_IP, t.get_port()),
            response = MASTER_STR)
        t.join()

        f = open("%s/bundle.lst" % server_result_dir, "r")
        bundle_list = f.read()
        f.close()

        #Upload bundle files to server
        for bundle in bundle_list:
            t = ResultUploader("%s/%s" % (server_result_dir, bundle)
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
        filelist = os.listdir("%s" % server_result_dir)
        for fil in filelist:
            found = re.match(pattern, fil)
            if found:
                filename = "%s/%s" % (server_result_dir, fil)
                f = open(filename, "r")
                content = f.read()
                f.close()
                srv.put(content, filename, pathname)

class ResultUploader(Thread):
    """
    Simple HTTP Server for uploading bundles
    """
    def __init__(self, filename):
    """
    if no filename specified, just get uploaded data
    """
        Thread.__init__(self)
        if filename:
            self.filename = filename
        self.data = ""
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(('', 0))

    def get_port(self):
        return self.s.getsockname()[1]

    def get_data(self):
        return self.data

    def run(self):
        self.s.listen(1)
        conn, addr = self.s.accept()
        while(1):
            #10KB per time
            data = conn.recv(10240)
            if not data: break
            self.data = self.data + data
            print data

        #if filename is given, store the data into a real file
        if self.filename:
            f = open(self.filename, 'w')
            f.write(self.data)
            f.close()
