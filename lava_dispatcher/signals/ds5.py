#!/usr/bin/python

# Copyright (C) 2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
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

import logging
import os
import StringIO
import tempfile

import pexpect

from lava_dispatcher.signals import PerTestCaseSignalHandler
from lava_dispatcher import utils


session_xml_template = '''\
<?xml version="1.0" encoding="US-ASCII" ?>
<session version="1" output_path="x" call_stack_unwinding="no" parse_debug_info="yes" high_resolution="no" buffer_mode="streaming" sample_rate="normal" duration="0" target_host="%(ip)s" target_port="8080" energy_cmd_line="">
</session>
'''

class signal_ds5(PerTestCaseSignalHandler):

    def __init__(self, client):
        super(signal_ds5, self).__init__(client)
        self.scratch_dir = utils.mkdtemp(
            self.client.context.config.lava_image_tmpdir)

    def _on_IP(self, ip):
        self.device_ip = ip

    def start_test_case(self, case_data):
        session_xml = session_xml_template % { 'ip': self.device_ip }
        (fd, name) = tempfile.mkstemp(
            prefix='session', suffix='.xml', dir=self.scratch_dir)
        with os.fdopen(fd, 'w') as f:
            f.write(session_xml)
        proc = utils.logging_spawn(
            '/usr/local/DS-5/bin/streamline -capture %s' % name)
        proc.logfile_read = self.log_file = StringIO.StringIO()
        idx = proc.expect(['Capture starting. Press ENTER to stop.', pexpect.EOF])
        if idx == 1:
            raise RuntimeError("streamline failed to start, output was %s" % self.log_file.getvalue())
        case_data['streamline_proc'] = proc

    def end_test_case(self, case_data):
        if 'streamline_proc' not in case_data:
            logging.warning("streamline failed to start?")
            return
        proc = case_data['streamline_proc']
        print repr(self.log_file.getvalue())
        proc.sendline()
        try:
            proc.expect('Created Streamline capture at "([^"]+)".\n')
        except:
            print repr(self.log_file.getvalue())
            raise
        apc_location = proc.match.group(1)
        proc.wait()
        print '!!!', apc_location
        apd_location = apc_location[:-1] + 'd'
        utils.logging_system(
            '/usr/local/DS-5/bin/streamline -analyze %s -o %s',
            apc_location, apd_location)
        report_location = apd_location[:-4] + '.txt'
        utils.logging_system(
            '/usr/local/DS-5/bin/streamline -report %s -o %s',
            apd_location, report_location)
        case_data['filename'] = report_location

    def postprocess_result(self, result, case_data):
        attrs = result.setdefault('attributes', {})
        attrs['streamline_location'] = case_data['filename']
        attrs['streamline_report'] = open(case_data['filename']).read()
