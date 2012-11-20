import subprocess

from lava_dispatcher.signals import SignalHandler

class ShellHooks(SignalHandler):

    def __init__(self, testdef_obj, device_config_vars, handlers):
        SignalHandler.__init__(self, testdef_obj)
        self._starttc_script = handlers.get('starttc')
        self._stoptc_script = handlers.get('stoptc')

    def starttc(self, test_case_id):
        # Set up a tmpdir for this test run!
        if self._starttc_script:
            subprocess.call([self._starttc_script, test_case_id])

    def stoptc(self, test_case_id):
        if self._stoptc_script:
            subprocess.call([self._stoptc_script, test_case_id])

