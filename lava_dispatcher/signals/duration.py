import datetime
import time

from json_schema_validator.extensions import timedelta_extension

from lava_dispatcher.signals import SignalHandler

class AddDuration(SignalHandler):

    def __init__(self, testdef_obj):
        SignalHandler.__init__(self, testdef_obj)
        self._starttimes = {}
        self._stoptimes = {}

    def starttc(self, test_case_id):
        self._starttimes[test_case_id] = time.time()

    def endtc(self, test_case_id):
        self._stoptimes[test_case_id] = time.time()

    def postprocess_test_run(self, test_run):
        for test_result in test_run['test_results']:
            tc_id = test_result.get('test_case_id')
            if not tc_id:
                continue
            if tc_id not in self._starttimes or tc_id not in self._stoptimes:
                continue
            delta = datetime.timedelta(
                seconds=self._stoptimes[tc_id] - self._starttimes[tc_id])
            test_result['duration'] = timedelta_extension.to_json(delta)
