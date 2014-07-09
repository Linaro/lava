import os
from StringIO import StringIO
import unittest
import yaml
import simplejson

from lava_dispatcher.pipeline import *
from lava_dispatcher.pipeline.job_actions.deploy.kvm import DeployAction, DeployKVM
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.config import get_device_config
from contextlib import GeneratorContextManager
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.tests.helper import LavaDispatcherTestCase
from lava_dispatcher.pipeline.job_actions.deploy.download import DownloaderAction


class TestBasicJob(LavaDispatcherTestCase):

    def test_basic_actions(self):
        factory = Factory()
        job = factory.create_fake_qemu_job()
        self.assertIsInstance(job, Job)
        self.assertIsInstance(job.pipeline, Pipeline)


class TestKVMSimulation(LavaDispatcherTestCase):

    def test_kvm_simulation(self):
        """
        Build a pipeline which simulates a KVM LAVA job
        without using the formal objects (to avoid validating
        data known to be broken). The details are entirely
        arbitrary.
        """
        pipe = Pipeline()
        action = Action()
        action.name = "deploy_linaro_image"
        action.description = "deploy action using preset subactions in an internal pipe"
        action.summary = "deploy_linaro_image"
        # deliberately unlikely location
        # a successful validation would need to use the cwd
        action.parameters = {"image": "file:///none/images/bad-kvm-debian-wheezy.img"}
        pipe.add_action(action)
        self.assertEqual(action.level, "1")
        deploy_pipe = Pipeline(action)
        action = Action()
        action.name = "downloader"
        action.description = "download image wrapper, including an internal retry pipe"
        action.summary = "downloader"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.1")
        # a formal RetryAction would contain a pre-built pipeline which can be inserted directly
        retry_pipe = Pipeline(action)
        action = Action()
        action.name = "wget"
        action.description = "do the download with retries"
        action.summary = "wget"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "1.1.1")
        action = Action()
        action.name = "checksum"
        action.description = "checksum the downloaded file"
        action.summary = "md5sum"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.2")
        action = Action()
        action.name = "overlay"
        action.description = "apply lava overlay"
        action.summary = "overlay"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.3")
        action = Action()
        action.name = "boot"
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
        action.name = "simulated"
        action.description = "lava test shell"
        action.summary = "simulated"
        # a formal lava test shell action would include an internal pipe
        # which would handle the run.sh
        pipe.add_action(action)
        self.assertEqual(action.level, "3")
        # a formal submit action would include an internal pipe to handle
        # the XMLRPC, including possible failure states and retries.
        action = Action()
        action.name = "submit"
        action.description = "submit results"
        action.summary = "submit"
        pipe.add_action(action)
        self.assertEqual(action.level, "4")
        self.assertEqual(len(pipe.describe().values()), 8)
        # uncomment to see the YAML dump of the pipeline.
        # print yaml.dump(pipe.describe())


class TestKVMBasicDeploy(LavaDispatcherTestCase):

    def setUp(self):
        super(TestKVMBasicDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_job('sample_jobs/kvm.yaml', self.config_dir)

    def test_deploy_job(self):
        self.assertEqual(self.job.parameters['output_dir'], self.config_dir)
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_kvm_basic_deploy(self):
        download = None
        mount = None
        checksum = None
        customise = None
        testdef = None
        unmount = None
        self.assertTrue(os.path.exists(self.job.parameters['output_dir']))
        self.assertEqual(len(self.job.pipeline.describe().values()), 10)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                # check parser has created a suitable deployment
                download = action.pipeline.children[action.pipeline][0]
                self.assertEqual(download.name, "download_action")
                checksum = action.pipeline.children[action.pipeline][1]
                self.assertEqual(checksum.name, "checksum_action")
                mount = action.pipeline.children[action.pipeline][2]
                self.assertEqual(mount.name, "mount_action")
                customise = action.pipeline.children[action.pipeline][3]
                self.assertEqual(customise.name, "customise")
                testdef = action.pipeline.children[action.pipeline][4]
                self.assertEqual(testdef.name, "test-definition")
                unmount = action.pipeline.children[action.pipeline][5]
                self.assertEqual(unmount.name, "umount")
                with self.assertRaises(IndexError):
                    type(action.pipeline.children[action.pipeline][6])
                # FIXME: deployment includes overlaying the test definitions
                # deploy needs to download with retry
                self.assertTrue(isinstance(action.pipeline.children[action.pipeline][0], RetryAction))
                # checksum downloaded file
                # assert d contains a checksum action
                # mount with offset
                # assert d contains a mount action
                # check for customisation (TBD later)
                # FIXME: ensure next step happens without needing to umount & remount!
                # ensure the test definition action is inside the mount pipeline
                # load test definitions into the image
                # umount
            elif isinstance(action, Action):
                pass
            else:
                print action
                self.fail("No deploy action found")
        download.parse()
        self.assertEqual(download.reader, download._http_stream)
        self.assertIsInstance(download, DownloaderAction)
        self.assertIsInstance(download.log_handler, logging.FileHandler)
        self.assertIsInstance(checksum.log_handler, logging.FileHandler)
        self.assertIsInstance(mount.log_handler, logging.FileHandler)
        self.assertIsInstance(customise.log_handler, logging.FileHandler)
        self.assertIsInstance(testdef.log_handler, logging.FileHandler)
        self.assertIsInstance(unmount.log_handler, logging.FileHandler)

    def test_kvm_basic_boot(self):
        for action in self.job.pipeline.actions:
            if action.name == 'boot':
                # get the action & populate it
                self.assertEqual(action.parameters['method'], 'kvm')

    def test_kvm_basic_test(self):
        for action in self.job.pipeline.actions:
            if action.name == 'test':
                # get the action & populate it
                self.assertEqual(len(action.parameters['definitions']), 2)

    def test_kvm_basic_submit(self):
        for action in self.job.pipeline.actions:
            if action.name == "submit_results":
                # get the action & populate it
                self.assertEqual(action.parameters['stream'], "/anonymous/codehelp/")
