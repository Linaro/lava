#!/usr/bin/python
import json
from lava.dispatcher.actions import BaseAction
from lava.dispatcher.config import LAVA_RESULT_DIR, MASTER_STR, LAVA_SERVER_IP
import socket
from threading import Thread
import time
import xmlrpclib
from subprocess import call

class cmd_submit_results_on_host(BaseAction):
    def run(self, server, stream):
        xmlrpc_url = "%s/xml-rpc/" % server
        srv = xmlrpclib.ServerProxy(xmlrpc_url,
                allow_none=True, use_datetime=True)

        client = self.client
        call("cd /tmp/%s/; ls *.bundle > bundle.lst" % LAVA_RESULT_DIR,
            shell=True)

        t = ResultUploader()
        t.start()
        call('cd /tmp/%s/; cat bundle.lst |nc %s %d' % (LAVA_RESULT_DIR,
            LAVA_SERVER_IP, t.get_port()), shell=True)
        t.join()

        bundle_list = t.get_data().strip().splitlines()
        #Upload bundle files to server
        for bundle in bundle_list:
            t = ResultUploader()
            t.start()
            call('cat /tmp/%s/%s | nc %s %s' % (LAVA_RESULT_DIR, bundle,
                LAVA_SERVER_IP, t.get_port()), shell = True)
            t.join()
            content = t.get_data()
            try:
                srv.put(content, bundle, stream)
            except xmlrpclib.Fault, err:
                print "xmlrpclib.Fault occurred"
                print "Fault code: %d" % err.faultCode
                print "Fault string: %s" % err.faultString
                
            # After uploading, remove the bundle file at the host side
            call('rm /tmp/%s/%s' % (LAVA_RESULT_DIR, bundle), shell=True)


class cmd_submit_results(BaseAction):
    all_bundles = []

    def run(self, server, stream, result_disk="testrootfs"):
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
            'mount /dev/disk/by-label/%s /mnt/root' % result_disk,
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
        #XXX: Odd problem where we sometimes get stuck here.  This is just
        #     a hacky workaround to see if it's a race
        time.sleep(60)
        client.run_shell_command(
            'cat bundle.lst |nc %s %d' % (LAVA_SERVER_IP, t.get_port()),
            response = MASTER_STR)
        t.join()

        bundle_list = t.get_data().strip().splitlines()

        #flush the serial log
        client.run_shell_command("")

        #Upload bundle files to server
        for bundle in bundle_list:
            t = ResultUploader()
            t.start()
            #XXX: Odd problem where we sometimes get stuck here.  This is just
            #     a hacky workaround to see if it's a race
            time.sleep(60)
            client.run_shell_command(
                'cat /tmp/%s/%s | nc %s %s' % (LAVA_RESULT_DIR, bundle,
                    LAVA_SERVER_IP, t.get_port()),
                response = MASTER_STR)
            t.join()
            content = t.get_data()

            self.all_bundles.append(json.loads(content))
            
        main_bundle = self.combine_bundles()
        main_bundle['test_runs'].append(self.context.test_data.get_test_run())
        for test_run in main_bundle['test_runs']:
            attributes = test_run.get('attributes',{})
            attributes.update(self.context.test_data.get_metadata())
            test_run['attributes'] = attributes
        json_bundle = json.dumps(main_bundle)
        srv.put(json_bundle, 'lava-dispatcher.bundle', stream)

    def combine_bundles(self):
        if not self.all_bundles:
            return {
                     "test_runs": [],
                     "format": "Dashboard Bundle Format 1.2"
                   }
        main_bundle = self.all_bundles.pop(0)
        test_runs = main_bundle['test_runs']
        for bundle in self.all_bundles:
            test_runs += bundle['test_runs']
        return main_bundle

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
        self.s.close()
