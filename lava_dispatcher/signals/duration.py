import datetime
import time

from json_schema_validator.extensions import timedelta_extension
from lava_dispatcher.signals import SignalHandler


class AddDuration(SignalHandler):

    def start_testcase(self, test_case_id):
        return {
            'starttime': time.time()
        }

    def end_testcase(self, test_case_id, data):
        data['endtime'] = time.time()

    def postprocess_test_result(self, test_result, data):
        delta = datetime.timedelta(seconds=data['endtime'] - data['starttime'])
        test_result['duration'] = timedelta_extension.to_json(delta)
