import logging
import os
import subprocess

from lava_dispatcher.downloader import download_image
from lava_dispatcher.signals import SignalHandler


class ArmProbe(SignalHandler):

    def __init__(self, testdef_obj, plotscript, probe_args=[]):
        SignalHandler.__init__(self, testdef_obj)

        self.scratch_dir = testdef_obj.context.client.target_device.scratch_dir
        self.plotscript = download_image(
            plotscript, testdef_obj.context, self.scratch_dir)
        os.chmod(self.plotscript, 755)  # make sure we can execute it

        # build up the command we'll use for running the probe
        config = testdef_obj.context.client.config
        self.aep_channels = config.arm_probe_channels
        self.aep_args = [
            config.arm_probe_binary, '-C', config.arm_probe_config]
        for c in self.aep_channels:
            self.aep_args.append('-c')
            self.aep_args.append(c)

        for arg in probe_args:
            self.aep_args.append(arg)

    def start_testcase(self, test_case_id):
        ofile = os.path.join(self.scratch_dir, '%s.out' % test_case_id)
        efile = os.path.join(self.scratch_dir, '%s.err' % test_case_id)
        ofile = open(ofile, 'w')
        efile = open(efile, 'w')

        proc = subprocess.Popen(
            self.aep_args, stdout=ofile, stderr=efile, stdin=subprocess.PIPE)
        proc.stdin.write(
            '# run from lava-test-shell with args: %r' % self.aep_args)
        proc.stdin.close()

        return {
            'process': proc,
            'logfile': ofile,
            'errfile': efile,
        }

    def end_testcase(self, test_case_id, data):
        proc = data['process']
        proc.terminate()

    def postprocess_test_result(self, test_result, data):
        tcid = test_result['test_case_id']
        logging.info('analyzing aep data for %s ...', tcid)

        lfile = data['logfile']
        efile = data['errfile']

        lfile.close()
        efile.close()

        with self._result_as_dir(test_result) as result_dir:
            args = [self.plotscript, tcid, lfile.name, efile.name]
            args.extend(self.aep_channels)

            if subprocess.call(args, cwd=result_dir) != 0:
                logging.warn('error calling plot script')
