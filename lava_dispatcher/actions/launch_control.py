#!/usr/bin/python

# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import json
import os
import shutil
import tarfile
from lava_dispatcher.actions import BaseAction
from lava_dispatcher.config import LAVA_RESULT_DIR
from lava_dispatcher.config import LAVA_IMAGE_TMPDIR
from lava_dispatcher.client import NetworkError
from lava_dispatcher.utils import download
from tempfile import mkdtemp
import time
import xmlrpclib

class cmd_submit_results_on_host(BaseAction):
    def run(self, server, stream):
        xmlrpc_url = "%s/xml-rpc/" % server
        srv = xmlrpclib.ServerProxy(xmlrpc_url,
                allow_none=True, use_datetime=True)

        #Upload bundle files to dashboard
        bundle_list = os.listdir("/tmp/%s" % LAVA_RESULT_DIR)
        for bundle_name in bundle_list:
            bundle = "/tmp/%s/%s" % (LAVA_RESULT_DIR, bundle_name)
            f = open(bundle)
            content = f.read()
            f.close()
            try:
                print >> self.context.oob_file, 'dashboard-put-result:', \
                      srv.put_ex(content, bundle, stream)
            except xmlrpclib.Fault, err:
                print "xmlrpclib.Fault occurred"
                print "Fault code: %d" % err.faultCode
                print "Fault string: %s" % err.faultString
            # After uploading, remove the bundle file at the host side
            os.remove(bundle)


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

        client.run_cmd_master('mkdir -p /mnt/root')
        client.run_cmd_master(
            'mount /dev/disk/by-label/%s /mnt/root' % result_disk)
        client.run_cmd_master('mkdir -p /tmp/%s' % LAVA_RESULT_DIR)
        client.run_cmd_master(
            'cp /mnt/root/%s/*.bundle /tmp/%s' % (LAVA_RESULT_DIR,
                LAVA_RESULT_DIR))
        client.run_cmd_master('umount /mnt/root')

        #Create tarball of all results
        client.run_cmd_master('cd /tmp')
        client.run_cmd_master(
            'tar czf /tmp/lava_results.tgz -C /tmp/%s .' % LAVA_RESULT_DIR)

        master_ip = client.get_master_ip()
        if master_ip == None:
            raise NetworkError("Getting master image IP address failed")
        # Set 80 as server port
        client.run_cmd_master('python -m SimpleHTTPServer 80 &> /dev/null &')
        time.sleep(3)

        result_tarball = "http://%s/lava_results.tgz" % master_ip
        tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        os.chmod(tarball_dir, 0755)

        # download test result with a retry mechanism
        # set retry timeout to 2mins
        now = time.time()
        timeout = 120
        while time.time() < now+timeout:
            try:
                result_path = download(result_tarball, tarball_dir)
            except:
                if time.time() >= now+timeout:
                    raise

        client.run_cmd_master('kill %1')

        tar = tarfile.open(result_path)
        for tarinfo in tar:
            if os.path.splitext(tarinfo.name)[1] == ".bundle":
                f = tar.extractfile(tarinfo)
                content = f.read()
                f.close()
                self.all_bundles.append(json.loads(content))
        tar.close()
        shutil.rmtree(tarball_dir)

        #flush the serial log
        client.run_shell_command("")

        main_bundle = self.combine_bundles()
        self.context.test_data.add_seriallog(
            self.context.client.get_seriallog())
        main_bundle['test_runs'].append(self.context.test_data.get_test_run())
        for test_run in main_bundle['test_runs']:
            attributes = test_run.get('attributes',{})
            attributes.update(self.context.test_data.get_metadata())
            test_run['attributes'] = attributes
        json_bundle = json.dumps(main_bundle)
        print >> self.context.oob_file, 'dashboard-put-result:', \
              srv.put_ex(json_bundle, 'lava-dispatcher.bundle', stream)

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

