#!/usr/bin/python
from lava.dispatcher.actions import BaseAction
from lava.dispatcher.config import LAVA_RESULT_DIR, MASTER_STR, LAVA_SERVER_IP
import socket
from threading import Thread
import xmlrpclib

class cmd_submit_results(BaseAction):
    def run(self, server, stream):
        """Submit test results to a launch-control server
        :param server: URL of the launch-control server
        :param stream: Stream on the launch-control server to save the result to
        """
        #Create l-c server connection
        xmlrpc_url = "%s/xml-rpc/" % server
        srv = xmlrpclib.ServerProxy(xmlrpc_url,
                allow_none=True, use_datetime=True)

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
            'mkdir -p /tmp/%s' % LAVA_RESULT_DIR, response = MASTER_STR)
        client.run_shell_command(
            'cp /mnt/root/%s/*.bundle /tmp/%s' % (LAVA_RESULT_DIR,
                LAVA_RESULT_DIR), response = MASTER_STR)
        client.run_shell_command('umount /mnt/root', response = MASTER_STR)

        #Upload bundle list-bundle.lst
        client.run_shell_command('cd /tmp/%s' % LAVA_RESULT_DIR,
            response = MASTER_STR)
        client.run_shell_command('ls *.bundle > bundle.lst',
            response = MASTER_STR)

        t = ResultUploader()
        t.start()
        client.run_shell_command(
            'cat bundle.lst |nc %s %d' % (LAVA_SERVER_IP, t.get_port()),
            response = MASTER_STR)
        t.join()

        bundle_list = t.get_data().strip().splitlines()
        #Upload bundle files to server
        client.seriallogger.quit_conmux()
        f = open("%s/%s" % (SERIAL_LOG_DIR, client.hostname), "r")
        serial_log = f.read()
        f.close()

        for bundle in bundle_list:
            t = ResultUploader()
            t.start()
            client.run_shell_command(
                'cat %s/%s | nc %s %s' % (LAVA_RESULT_DIR, bundle,
                    LAVA_SERVER_IP, t.get_port()),
                response = MASTER_STR)
            t.join()
            content = t.get_data()
            #attach serial log
            content = self._attach_seriallog(content, serial_log)
            srv.put(content, bundle, stream)

    def _attach_seriallog(self, content, serial_log):
        """
        Add serial log to the end of "test_result" list as a field "serial_log"
        """
        start = content.rindex("test_results")
        end = content.index("],", start)
        idx = content.rindex("}", start, end)
        #left part before '],', the end of "test_results" field
        s1 = content[0:idx+1]
        #right part after '}', start from '],'
        s2 = content[idx+1:len(content)]
        s = ",{\"serial_log\":\"" + serial_log + "\"}"
        content = s1 + s + s2
        return content

class ResultUploader(Thread):
    """
    Simple HTTP Server for uploading bundles
    """
    def __init__(self):
        """
        if no filename specified, just get uploaded data
        """
        Thread.__init__(self)
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
            if not data:
                break
            self.data = self.data + data
