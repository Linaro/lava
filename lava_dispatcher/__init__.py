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
import json
import traceback
from uuid import uuid1
import base64
import pexpect

from lava_dispatcher.actions import get_all_cmds
from lava_dispatcher.config import get_config, get_device_config
from lava_dispatcher.client import LavaClient, CriticalError, GeneralError
from lava_dispatcher.android_client import LavaAndroidClient

__version__ = "0.3.1"

class LavaTestJob(object):
    def __init__(self, job_json, oob_file):
        self.job_status = 'pass'
        self.load_job_data(job_json)
        dispatcher_config = get_config("lava-dispatcher")
        self.context = LavaContext(
            self.target, self.image_type, dispatcher_config, oob_file,
            self.job_data)

    def load_job_data(self, job_json):
        self.job_data = json.loads(job_json)

    @property
    def target(self):
        return self.job_data['target']

    @property
    def image_type(self):
        return self.job_data.get('image_type')

    def run(self):
        lava_commands = get_all_cmds()

        if self.job_data['actions'][-1]['command'].startswith("submit_results"):
            submit_results = self.job_data['actions'].pop(-1)
        else:
            submit_results = None

        metadata = {
            'target.hostname': self.target,
        }

        if 'device_type' in self.job_data:
            metadata['target.device_type'] = self.job_data['device_type']
        self.context.test_data.add_metadata(metadata)

        try:
            for cmd in self.job_data['actions']:
                params = cmd.get('parameters', {})
                metadata = cmd.get('metadata', {})
                self.context.test_data.add_metadata(metadata)
                action = lava_commands[cmd['command']](self.context)
                try:
                    status = 'fail'
                    action.run(**params)
                except CriticalError as err:
                    raise
                except (pexpect.TIMEOUT, GeneralError) as err:
                    pass
                except Exception as err:
                    raise
                else:
                    status = 'pass'
                finally:
                    err_msg = ""
                    if status == 'fail':
                        err_msg = "Lava failed at action %s with error: %s\n" %\
                                  (cmd['command'], err)
                        if cmd['command'] == 'lava_test_run':
                            err_msg += "Lava failed on test: %s" %\
                                       params.get('test_name', "Unknown")
                        err_msg = err_msg + traceback.format_exc()
                        # output to both serial log and logfile
                        self.context.client.sio.write(err_msg)
                    else:
                        err_msg = ""
                    self.context.test_data.add_result(
                        cmd['command'], status, err_msg)
        except:
            #Capture all user-defined and non-user-defined critical errors
            self.context.test_data.job_status='fail'
            raise
        finally:
            if submit_results:
                params = submit_results.get('parameters', {})
                action = lava_commands[submit_results['command']](
                    self.context)
                action.run(**params)


class LavaContext(object):
    def __init__(self, target, image_type, dispatcher_config, oob_file, job_data):
        self.config = dispatcher_config
        self.job_data = job_data
        device_config = get_device_config(target)
        if device_config.get('client_type') != 'conmux':
            raise RuntimeError(
                "this version of lava-dispatcher only supports conmux "
                "clients, not %r" % device_config.get('client_type'))
        if image_type == "android":
            self._client = LavaAndroidClient(self, device_config)
        else:
            self._client = LavaClient(self, device_config)
        self.test_data = LavaTestData()
        self.oob_file = oob_file

    @property
    def client(self):
        return self._client

    @property
    def lava_server_ip(self):
        return self.config.get("LAVA_SERVER_IP")

    @property
    def lava_image_tmpdir(self):
        return self.config.get("LAVA_IMAGE_TMPDIR")

    @property
    def lava_image_url(self):
        return self.config.get("LAVA_IMAGE_URL")

    @property
    def lava_result_dir(self):
        if self.client.android_result_dir:
            return self.client.android_result_dir
        return self.config.get("LAVA_RESULT_DIR")

    @property
    def lava_cachedir(self):
        return self.config.get("LAVA_CACHEDIR")


class LavaTestData(object):
    def __init__(self, test_id='lava'):
        self.job_status = 'pass'
        self.metadata = {}
        self._test_run = { 'test_results':[], 'attachments':[] }
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

    def add_result(self, test_case_id, result, message=""):
        result_data = {
            'test_case_id': test_case_id,
            'result': result,
            'message': message
            }
        self._test_run['test_results'].append(result_data)

    def add_attachment(self, attachment):
        self._test_run['attachments'].append(attachment)

    def add_metadata(self, metadata):
        self.metadata.update(metadata)

    def get_metadata(self):
        return self.metadata

    def get_test_run(self):
        self.add_result('job_complete', self.job_status)
        return self._test_run

    def add_seriallog(self, serial_log):
        """
        Add serial log to the "attachments" field, it aligns bundle 1.2 format
        """
        serial_log_base64 = base64.b64encode(serial_log)
        attachment = {
                "pathname": "serial.log",
                "mime_type": "text/plain",
                "content": serial_log_base64 }
        self.add_attachment(attachment)

