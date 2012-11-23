from glob import glob
import logging
import shutil
import subprocess
import os

from lava_dispatcher.signals import SignalHandler
from lava_dispatcher.utils import mkdtemp


class ShellHooks(SignalHandler):

    def __init__(self, testdef_obj, handlers={}, device_config_vars={},
                 host_deps=None):
        SignalHandler.__init__(testdef_obj)
        self.code_dir = mkdtemp()
        self.result_dir = mkdtemp()
        self.handlers = handlers
        for filepath in glob(os.path.join(testdef_obj.repo, '*')):
            shutil.copy2(filepath, self.code_dir)

    def _invoke_hook(self, name, working_dir, args=[]):
        script_name = self.handlers.get(name)
        if not script_name:
            return
        script = os.path.join(self.code_dir, script_name)
        if not os.path.exists(script):
            logging.warning("handler script %s not found", script_name)
            return
        status = subprocess.call([script] + args, cwd=working_dir)
        if status != 0:
            logging.warning(
                "%s handler script exited with code %s", name, status)

    def start_testcase(self, test_case_id):
        result_dir = os.path.join(self.result_dir, test_case_id)
        os.mkdir(result_dir)
        self._invoke_hook('start_testcase', result_dir)

    def stop_testcase(self, test_case_id, data):
        result_dir = os.path.join(self.result_dir, test_case_id)
        self._invoke_hook('stop_testcase', result_dir)

    def postprocess_test_result(self, test_result, case_data):
        test_case_id = test_result['test_case_id']
        result_dir = os.path.join(self.result_dir, test_case_id)
        self._invoke_hook('postprocess_test_result', result_dir, ['a'])

