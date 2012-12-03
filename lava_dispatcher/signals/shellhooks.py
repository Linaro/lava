import logging
import shutil
import subprocess
import os
import tempfile

from lava_dispatcher.lava_test_shell import _result_to_dir, _result_from_dir
from lava_dispatcher.signals import SignalHandler
from lava_dispatcher.utils import mkdtemp


class ShellHooks(SignalHandler):

    def __init__(self, testdef_obj, handlers={}, device_config_vars={},
                 host_deps=None):
        SignalHandler.__init__(self, testdef_obj)
        self.result_dir = mkdtemp()
        self.handlers = handlers
        self.code_dir = os.path.join(mkdtemp(), 'code')
        shutil.copytree(testdef_obj.repo, self.code_dir)

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
        case_dir = os.path.join(self.result_dir, test_case_id)
        os.mkdir(case_dir)
        self._invoke_hook('start_testcase', case_dir)
        return case_dir

    def stop_testcase(self, test_case_id, case_dir):
        self._invoke_hook('stop_testcase', case_dir)

    def postprocess_test_result(self, test_result, case_dir):
        test_case_id = test_result['test_case_id']
        scratch_dir = tempfile.mkdtemp()
        try:
            result_dir = os.path.join(scratch_dir, test_case_id)
            os.mkdir(result_dir)
            _result_to_dir(test_result, result_dir)
            self._invoke_hook('postprocess_test_result', case_dir, [result_dir])
            test_result.clear()
            test_result.update(_result_from_dir(result_dir))
        finally:
            shutil.rmtree(scratch_dir)

