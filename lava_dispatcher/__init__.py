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

import sys
from datetime import datetime
import json
import traceback
from uuid import uuid1
import base64
import pexpect

from lava_dispatcher.actions import get_all_cmds
from lava_dispatcher.client import LavaClient, CriticalError, GeneralError
from lava_dispatcher.android_client import LavaAndroidClient
from lava_dispatcher.qemu_client import LavaQEMUClient
from lava_dispatcher.ssh_client import LavaSSHClient

__version__ = "0.1.0"

class LavaTestJob(object):
    def __init__(self, job_json):
        self.job_status = 'pass'
        self.load_job_data(job_json)
        self.context = LavaContext(self.target, self.image_type, self.target_type)

    def load_job_data(self, job_json):
        self.job_data = json.loads(job_json)

    @property
    def target(self):
        return self.job_data.get('target')

    @property
    def image_type(self):
        return self.job_data.get('image_type')

    @property
    def target_type(self):
        return self.job_data.get('target_type')

    def run(self):
        lava_commands = get_all_cmds()

        if self.job_data['actions'][-1]['command'] == 'submit_results':
            submit_results = self.job_data['actions'].pop(-1)
        else:
            submit_results = None

        try:
            for cmd in self.job_data['actions']:
                params = cmd.get('parameters', {})
                metadata = cmd.get('metadata', {})
                metadata['target.hostname'] = self.target
                self.context.test_data.add_metadata(metadata)
                action = lava_commands[cmd['command']](self.context)
                except_str = ""
                try:
                    status = 'fail'
                    action.run(**params)
                except CriticalError as err:
                    except_str = str(err)
                    raise
                except (pexpect.TIMEOUT, GeneralError) as err:
                    except_str = str(err)
                    pass
                except Exception as err:
                    except_str = str(err)
                    raise
                else:
                    status = 'pass'
                finally:
                    err_msg = ""
                    command = cmd['command']
                    if status == 'fail':
                        err_msg = "Lava failed at action %s with error: %s\n" %\
                                  (command, except_str)
                        if command == 'lava_test_run':
                            err_msg += "Lava failed on test: %s" %\
                                       params.get('test_name')
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        err_msg += repr(traceback.format_tb(exc_traceback))
                        # output to both serial log and logfile
                        self.context.client.sio.write(err_msg)
                    self.context.test_data.add_result(command, status, err_msg)

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
    def __init__(self, target, image_type, target_type):
        if image_type == "android":
            self._client = LavaAndroidClient(target)
        elif target_type == "qemu":
            self._client = LavaQEMUClient(target)
        elif target_type == "ssh":
            self._client = LavaSSHClient(target)
        else:
            # conmux / serial
            self._client = LavaClient(target)
        self.test_data = LavaTestData()

    @property
    def client(self):
        return self._client


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

    @property
    def job_status(self):
        return self._job_status

    @job_status.setter
    def job_status(self, status):
        self._job_status = status

    def add_result(self, test_case_id, result, message=""):
        result_data = {'test_case_id': test_case_id, 'result': result, \
               'message': message}
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

