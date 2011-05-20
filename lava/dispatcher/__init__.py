#!/usr/bin/python
from datetime import datetime
import json
from lava.dispatcher.actions import get_all_cmds
from lava.dispatcher.client import LavaClient
from uuid import uuid1

class LavaTestJob(object):
    def __init__(self, job_json):
        self.job_status = 'pass'
        self.load_job_data(job_json)
        self.context = LavaContext(self.target)

    def load_job_data(self, job_json):
        self.job_data = json.loads(job_json)

    @property
    def target(self):
        return self.job_data['target']

    def run(self):
        lava_commands = get_all_cmds()

        for cmd in self.job_data['actions']:
            try:
                params = cmd.get('parameters', {})
                metadata = cmd.get('metadata', {})
                self.context.test_data.add_metadata(metadata)
                action = lava_commands[cmd['command']](self.context)
                action.run(**params)
            except:
                #FIXME: need to capture exceptions for later logging
                #and try to continue from where we left off
                self.context.test_data.job_status='fail'
                raise


class LavaContext(object):
    def __init__(self, target):
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

    def add_result(self, test_case_id, result):
        result_data = { 'test_case_id': test_case_id, 'result':result }
        self._test_run['test_results'].append(result_data)

    def add_attachment(self, attachment):
        self._test_run['attachments'].append(attachment)

    def add_metadata(self, metadata):
        self.metadata.update(metadata)

    def get_metadata(self):
        return self.metadata
