from ConfigParser import NoOptionError
import logging
import shutil
import subprocess
import os
import tempfile
import lava_dispatcher.utils as utils

from lava_dispatcher.utils import read_content
from lava_dispatcher.signals import SignalHandler
from lava_dispatcher.test_data import create_attachment


class ShellHooks(SignalHandler):

    def __init__(self, testdef_obj, handlers=None, device_config_vars=None):
        if not device_config_vars:
            device_config_vars = {}
        if not handlers:
            handlers = {}
        SignalHandler.__init__(self, testdef_obj)
        self.result_dir = utils.mkdtemp()
        self.handlers = handlers
        self.scratch_dir = utils.mkdtemp()
        self.code_dir = os.path.join(self.scratch_dir, 'code')
        shutil.copytree(testdef_obj.repo, self.code_dir)
        device_config = testdef_obj.context.client.target_device.config
        self.our_env = os.environ.copy()
        for env_var, config_var in device_config_vars.iteritems():
            try:
                config_value = device_config.cp.get('__main__', config_var)
            except NoOptionError:
                logging.warning(
                    "No value found for device config %s; leaving %s unset "
                    "in environment", config_var, env_var)
            else:
                self.our_env[env_var] = config_value

    def _invoke_hook(self, name, working_dir, args=None):
        if not args:
            args = []
        script_name = self.handlers.get(name)
        if not script_name:
            return
        script = os.path.join(self.code_dir, script_name)
        if not os.path.exists(script):
            logging.warning("handler script %s not found", script_name)
            return
        (fd, path) = tempfile.mkstemp(dir=self.code_dir)
        status = subprocess.call(
            [script] + args, cwd=working_dir, env=self.our_env,
            stdout=fd, stderr=subprocess.STDOUT)
        if status != 0:
            logging.warning(
                "%s handler script exited with code %s", name, status)
        return path

    def start_testcase(self, test_case_id):
        case_dir = os.path.join(self.result_dir, test_case_id)
        utils.ensure_directory(case_dir)
        case_data = {'case_dir': case_dir}
        case_data['start_testcase_output'] = self._invoke_hook(
            'start_testcase', case_dir)
        return case_data

    def end_testcase(self, test_case_id, case_data):
        case_data['end_testcase_output'] = self._invoke_hook(
            'end_testcase', case_data['case_dir'])

    def postprocess_test_result(self, test_result, case_data):
        with self._result_as_dir(test_result) as result_dir:
            case_data['postprocess_test_result_output'] = self._invoke_hook(
                'postprocess_test_result', case_data['case_dir'], [result_dir])

        for key in 'start_testcase_output', 'end_testcase_output', \
                'postprocess_test_result_output':
            path = case_data.get(key)
            if path is None:
                continue
            content = read_content(path, ignore_missing=True)
            if content:
                test_result['attachments'].append(
                    create_attachment(key + '.txt', read_content(path)))
