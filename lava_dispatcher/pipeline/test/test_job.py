import os
from StringIO import StringIO
import unittest
import yaml
import simplejson

from lava_dispatcher.pipeline import *
from lava_dispatcher.pipeline.parser import JobParser


class TestJob(unittest.TestCase):

    def test_basic_actions(self):
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/basics.yaml')
        self.sample_job_data = open(sample_job_file)
        self.parser = JobParser()
        job = self.parser.parse(self.sample_job_data)

        self.assertIsInstance(job, Job)
        self.assertIsInstance(job.pipeline, Pipeline)

    def test_kvm_simulation(self):
        """
        Build a pipeline which simulates a KVM LAVA job
        without using the formal objects (to avoid validating
        data known to be broken). The details are entirely
        arbitrary.
        """
        pipe = Pipeline()
        action = Action()
        action.description = "deploy action using preset subactions in an internal pipe"
        action.summary = "deploy_linaro_image"
        # deliberately unlikely location
        # a successful validation would need to use the cwd
        action.parameters = {"image": "file:///none/images/bad-kvm-debian-wheezy.img"}
        pipe.add_action(action)
        self.assertEqual(action.level, "1")
        deploy_pipe = Pipeline(action)
        action = Action()
        action.description = "download image wrapper, including an internal retry pipe"
        action.summary = "downloader"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.1")
        # a formal RetryAction would contain a pre-built pipeline which can be inserted directly
        retry_pipe = Pipeline(action)
        action = Action()
        action.description = "do the download with retries"
        action.summary = "wget"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "1.1.1")
        action = Action()
        action.description = "checksum the downloaded file"
        action.summary = "md5sum"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.2")
        action = Action()
        action.description = "apply lava overlay"
        action.summary = "overlay"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.3")
        action = Action()
        action.description = "boot image"
        action.summary = "qemu"
        # cmd_line built from device configuration
        action.parameters = {
            'cmd_line': [
                'qemu-system-x86_64',
                '-machine accel=kvm:tcg',
                '-hda'
                '%s' % "tbd",
                '-nographic',
                '-net',
                'nic,model=virtio'
                '-net user'
            ]
        }
        pipe.add_action(action)
        self.assertEqual(action.level, "2")

        action = Action()
        action.description = "lava test shell"
        action.summary = "simulated"
        # a formal lava test shell action would include an internal pipe
        # which would handle the run.sh
        pipe.add_action(action)
        self.assertEqual(action.level, "3")
        # a formal submit action would include an internal pipe to handle
        # the XMLRPC, including possible failure states and retries.
        action = Action()
        action.description = "submit results"
        action.summary = "submit"
        pipe.add_action(action)
        self.assertEqual(action.level, "4")
        self.assertEqual(len(pipe.describe().values()), 8)
        # uncomment to see the YAML dump of the pipeline.
        #print yaml.dump(pipe.describe())
