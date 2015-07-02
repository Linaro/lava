# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os
import glob
import unittest
import yaml

from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.action import Pipeline, Action, JobError
from lava_dispatcher.pipeline.test.test_basic import Factory, pipeline_reference
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.boot.qemu import BootAction


class TestBasicJob(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_basic_actions(self):
        factory = Factory()
        job = factory.create_fake_qemu_job(mkdtemp())
        if not job:
            return unittest.skip("not all deployments have been implemented")
        self.assertIsInstance(job, Job)
        self.assertIsInstance(job.pipeline, Pipeline)


class TestKVMSimulation(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_kvm_simulation(self):  # pylint: disable=too-many-statements
        """
        Build a pipeline which simulates a KVM LAVA job
        without using the formal objects (to avoid validating
        data known to be broken). The details are entirely
        arbitrary.
        """
        factory = Factory()
        job = factory.create_kvm_job('sample_jobs/kvm.yaml')
        pipe = Pipeline()
        action = Action()
        action.name = "deploy_linaro_image"
        action.description = "deploy action using preset subactions in an internal pipe"
        action.summary = "deploy_linaro_image"
        action.job = job
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
        action.job = job
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.1")
        # a formal RetryAction would contain a pre-built pipeline which can be inserted directly
        retry_pipe = Pipeline(action)
        action = Action()
        action.name = "wget"
        action.description = "do the download with retries"
        action.summary = "wget"
        action.job = job
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "1.1.1")
        action = Action()
        action.name = "checksum"
        action.description = "checksum the downloaded file"
        action.summary = "md5sum"
        action.job = job
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.2")
        action = Action()
        action.name = "overlay"
        action.description = "apply lava overlay"
        action.summary = "overlay"
        action.job = job
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.3")
        action = Action()
        action.name = "boot"
        action.description = "boot image"
        action.summary = "qemu"
        action.job = job
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
        action.job = job
        # a formal lava test shell action would include an internal pipe
        # which would handle the run.sh
        pipe.add_action(action)
        self.assertEqual(action.level, "3")
        # just a fake action
        action = Action()
        action.name = "fake"
        action.description = "faking results"
        action.summary = "fake action"
        action.job = job
        pipe.add_action(action)
        self.assertEqual(action.level, "4")
        self.assertEqual(len(pipe.describe()), 4)


class TestKVMBasicDeploy(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKVMBasicDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm.yaml', mkdtemp())

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = pipeline_reference('kvm.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_overlay(self):
        overlay = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, DeployAction):
                overlay = action.pipeline.children[action.pipeline][3]
        self.assertIsNotNone(overlay)
        # these tests require that lava-dispatcher itself is installed, not just running tests from a git clone
        self.assertTrue(os.path.exists(overlay.lava_test_dir))
        self.assertIsNot(overlay.lava_test_dir, '/')
        self.assertNotIn('lava_multi_node_test_dir', dir(overlay))
        self.assertNotIn('lava_multi_node_cache_file', dir(overlay))
        self.assertNotIn('lava_lmp_test_dir', dir(overlay))
        self.assertNotIn('lava_lmp_cache_file', dir(overlay))
        self.assertIsNotNone(overlay.parameters['deployment_data']['lava_test_results_dir'])
        self.assertIsNotNone(overlay.parameters['deployment_data']['lava_test_sh_cmd'])
        self.assertEqual(overlay.parameters['deployment_data']['distro'], 'debian')
        self.assertIsNotNone(overlay.parameters['deployment_data']['lava_test_results_part_attr'])
        self.assertIsNotNone(glob.glob(os.path.join(overlay.lava_test_dir, 'lava-*')))

    def test_boot(self):
        for action in self.job.pipeline.actions:
            if isinstance(action, BootAction):
                # get the action & populate it
                self.assertEqual(action.parameters['method'], 'qemu')

    def test_testdefinitions(self):
        for action in self.job.pipeline.actions:
            if action.name == 'test':
                # get the action & populate it
                self.assertEqual(len(action.parameters['definitions']), 2)


class TestKVMQcow2Deploy(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKVMQcow2Deploy, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-qcow2.yaml', mkdtemp())

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = pipeline_reference('kvm-qcow2.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)


class TestKVMDownloadLocalDeploy(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKVMDownloadLocalDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-local.yaml', mkdtemp())

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = pipeline_reference('kvm-local.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))


class TestKVMInlineTestDeploy(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKVMInlineTestDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-inline.yaml', mkdtemp())

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_pipeline(self):
        description_ref = pipeline_reference('kvm-inline.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

        self.assertEqual(len(self.job.pipeline.describe()), 4)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                overlay = action.pipeline.children[action.pipeline][3]
                testdef = overlay.internal_pipeline.actions[1]
                inline_repo = testdef.internal_pipeline.actions[0]
                break

            # Test the InlineRepoAction directly
            location = mkdtemp()
            inline_repo.data['lava-overlay'] = {'location': location}
            inline_repo.data['test-definition'] = {'overlay_dir': location}

            inline_repo.run(None)
            yaml_file = os.path.join(location, 'tests/0_smoke-tests-inline/inline/smoke-tests-basic.yaml')
            self.assertTrue(os.path.exists(yaml_file))
            with open(yaml_file, 'r') as f_in:
                testdef = yaml.load(f_in)
            expected_testdef = {'metadata':
                                {'description': 'Basic system test command for Linaro Ubuntu images',
                                 'devices': ['panda', 'panda-es', 'arndale', 'vexpress-a9', 'vexpress-tc2'],
                                 'format': 'Lava-Test Test Definition 1.0',
                                 'name': 'smoke-tests-basic',
                                 'os': ['ubuntu'],
                                 'scope': ['functional'],
                                 'yaml_line': 39},
                                'run': {'steps': ['lava-test-case linux-INLINE-pwd --shell pwd',
                                                  'lava-test-case linux-INLINE-uname --shell uname -a',
                                                  'lava-test-case linux-INLINE-vmstat --shell vmstat',
                                                  'lava-test-case linux-INLINE-ifconfig --shell ifconfig -a',
                                                  'lava-test-case linux-INLINE-lscpu --shell lscpu',
                                                  'lava-test-case linux-INLINE-lsusb --shell lsusb',
                                                  'lava-test-case linux-INLINE-lsb_release --shell lsb_release -a'],
                                        'yaml_line': 53},
                                'yaml_line': 38}
            self.assertEqual(testdef, expected_testdef)
