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
import time
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
        proc = case_data['streamline_proc'] = pexpect.pexpect(
            '/usr/local/DS-5/bin/streamline -capture %s' % name)
        proc.expect('Capture starting. Press ENTER to stop.')

    def end_test_case(self, case_data):
        proc = case_data['streamline_proc']
        proc.sendline()
        proc.expect('Created Streamline capture at "([^"]+)".\n')
        filename = proc.match.group(1)
        proc.wait()
        print '!!!', filename
        case_data['filename'] = filename

    def postprocess_result(self, result, case_data):
        attrs = result.setdefault('attributes', {})
        attrs['streamline_location'] = case_data['filename']
