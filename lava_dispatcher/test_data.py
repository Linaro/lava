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

from datetime import datetime
from uuid import uuid1
import base64


def create_attachment(pathname, content, mime_type='text/plain'):
    return {
        'pathname': pathname,
        'mime_type': mime_type,
        'content': base64.b64encode(content),
    }


class LavaTestData(object):
    def __init__(self, test_id='lava'):
        self.job_status = 'pass'
        self.metadata = {}
        self._test_run = {'test_results': [], 'attachments': [], 'tags': []}
        self._test_run['test_id'] = test_id
        self._assign_date()
        self._assign_uuid()

    def _assign_date(self):
        TIMEFORMAT = '%Y-%m-%dT%H:%M:%SZ'
        self._test_run['time_check_performed'] = False
        self._test_run['analyzer_assigned_date'] = datetime.strftime(
            datetime.now(), TIMEFORMAT)

    def _assign_uuid(self):
        self._test_run['analyzer_assigned_uuid'] = str(uuid1())

    def add_result(self, test_case_id, result, measurement="", units="",
                   message=""):
        result_data = {
            'test_case_id': test_case_id,
            'result': result,
            'measurement': measurement,
            'units': units,
            'message': message
        }
        self._test_run['test_results'].append(result_data)

    def add_attachments(self, attachments):
        self._test_run['attachments'].extend(attachments)

    def add_tag(self, tag):
        self._test_run['tags'].append(tag)

    def add_tags(self, tags):
        for tag in tags:
            self.add_tag(tag)

    def add_metadata(self, metadata):
        self.metadata.update(metadata)

    def get_metadata(self):
        return self.metadata

    def get_test_run(self):
        self.add_result('job_complete', self.job_status)
        return self._test_run
