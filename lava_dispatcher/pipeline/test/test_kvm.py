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
import time
import unittest
import yaml
import pexpect

from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    JobError,
    InfrastructureError,
)
from lava_dispatcher.pipeline.test.test_basic import Factory, pipeline_reference, StdoutTestCase
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.boot.qemu import BootAction
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.test.test_messages import FakeConnection
from lava_dispatcher.pipeline.utils.messages import LinuxKernelMessages
from lava_dispatcher.pipeline.test.test_defs import allow_missing_path, check_missing_path
from lava_dispatcher.pipeline.utils.shell import infrastructure_error

# pylint: disable=invalid-name


class TestBasicJob(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def test_basic_actions(self):
        factory = Factory()
        job = factory.create_fake_qemu_job(mkdtemp())
        if not job:
            return unittest.skip("not all deployments have been implemented")
        self.assertIsInstance(job, Job)
        self.assertIsInstance(job.pipeline, Pipeline)


class TestKVMSimulation(StdoutTestCase):  # pylint: disable=too-many-public-methods

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


class TestKVMBasicDeploy(StdoutTestCase):  # pylint: disable=too-many-public-methods

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
        deploy = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        overlay = [action for action in deploy.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        self.assertIn('persistent-nfs-overlay', [action.name for action in overlay.internal_pipeline.actions])
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

    def test_validate(self):
        try:
            allow_missing_path(self.job.pipeline.validate_actions, self, 'qemu-system-x86_64')
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_overlay(self):
        overlay = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, DeployAction):
                overlay = action.pipeline.actions[3]
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
                self.assertEqual(action.parameters['prompts'], ['linaro-test', 'root@debian:~#'])
                params = action.parameters.get('auto_login', None)

                if 'login_prompt' in params:
                    self.assertEqual(params['login_prompt'], 'login:')
                if 'username' in params:
                    self.assertEqual(params['username'], 'root')

    def test_testdefinitions(self):
        for action in self.job.pipeline.actions:
            if action.name == 'test':
                # get the action & populate it
                self.assertEqual(len(action.parameters['definitions']), 2)


class TestKVMQcow2Deploy(StdoutTestCase):  # pylint: disable=too-many-public-methods

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

    def test_validate(self):
        try:
            allow_missing_path(self.job.pipeline.validate_actions, self, 'qemu-system-x86_64')
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)


class TestKVMDownloadLocalDeploy(StdoutTestCase):  # pylint: disable=too-many-public-methods

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


def prepare_test_connection():
    logfile = os.path.join(os.path.dirname(__file__), 'kernel.txt')
    if not os.path.exists(logfile):
        raise OSError("Missing test support file.")
    child = pexpect.spawn('cat', [logfile])
    message_list = LinuxKernelMessages.get_kernel_prompts()
    return FakeConnection(child, message_list)


class TestKVMInlineTestDeploy(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKVMInlineTestDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-inline.yaml', mkdtemp())

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        except InfrastructureError:
            pass
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_extra_options(self):
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/kvm01.yaml'))
        kvm_yaml = os.path.join(os.path.dirname(__file__), 'sample_jobs/kvm-inline.yaml')
        with open(kvm_yaml) as sample_job_data:
            job_data = yaml.load(sample_job_data)
        device['actions']['boot']['methods']['qemu']['parameters']['extra'] = yaml.load("""
                  - -smp
                  - 1
                  - -global
                  - virtio-blk-device.scsi=off
                  - -device virtio-scsi-device,id=scsi
                  - --append "console=ttyAMA0 root=/dev/vda rw"
                  """)
        self.assertIsInstance(device['actions']['boot']['methods']['qemu']['parameters']['extra'][1], int)
        parser = JobParser()
        job = parser.parse(yaml.dump(job_data), device, 4212, None, "",
                           output_dir='/tmp/')
        job.validate()
        boot_image = [action for action in job.pipeline.actions if action.name == 'boot_image_retry'][0]
        boot_qemu = [action for action in boot_image.internal_pipeline.actions if action.name == 'boot_qemu_image'][0]
        qemu = [action for action in boot_qemu.internal_pipeline.actions if action.name == 'execute-qemu'][0]
        self.assertIsInstance(qemu.sub_command, list)
        [self.assertIsInstance(item, str) for item in qemu.sub_command]  # pylint: disable=expression-not-assigned
        self.assertIn('virtio-blk-device.scsi=off', qemu.sub_command)
        self.assertIn('1', qemu.sub_command)
        self.assertNotIn(1, qemu.sub_command)

    def test_pipeline(self):
        description_ref = pipeline_reference('kvm-inline.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

        self.assertEqual(len(self.job.pipeline.describe()), 4)
        inline_repo = None
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertIsNotNone(action.internal_pipeline.actions[2])
                overlay = action.pipeline.actions[2]
                self.assertIsNotNone(overlay.internal_pipeline.actions[2])
                testdef = overlay.internal_pipeline.actions[2]
                self.assertIsNotNone(testdef.internal_pipeline.actions[0])
                inline_repo = testdef.internal_pipeline.actions[0]
                break
        # Test the InlineRepoAction directly
        self.assertIsNotNone(inline_repo)
        location = mkdtemp()
        # other actions have not been run, so fake up
        inline_repo.set_namespace_data(action='test', label='results', key='lava_test_results_dir', value=location)
        inline_repo.set_namespace_data(action='test', label='test-definition', key='overlay_dir', value=location)
        inline_repo.set_namespace_data(action='test', label='shared', key='location', value=location)
        inline_repo.set_namespace_data(action='test', label='test-definiton', key='overlay_dir', value=location)

        inline_repo.run(None, None)
        yaml_file = os.path.join(location, '0/tests/0_smoke-tests-inline/inline/smoke-tests-basic.yaml')
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
        self.assertEqual(set(testdef), set(expected_testdef))


class TestAutoLogin(StdoutTestCase):

    def setUp(self):
        super(TestAutoLogin, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-inline.yaml', mkdtemp())
        self.max_end_time = time.time() + 30

    def test_autologin_prompt_patterns(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)
        self.job.validate()

        bootaction = [action for action in self.job.pipeline.actions if action.name == 'boot_image_retry'][0]
        autologinaction = [action for action in bootaction.internal_pipeline.actions if action.name == 'auto-login-action'][0]

        autologinaction.parameters.update({'auto_login': {'login_prompt': 'login:',
                                                          'username': 'root'},
                                           'prompts': ['root@debian:~#']})

        # initialise the first Connection object, a command line shell
        shell_connection = prepare_test_connection()
        autologinaction.set_namespace_data(
            action="deploy-device-env", label='environment',
            key='line_separator', value='testsep')

        # Test the AutoLoginAction directly
        conn = autologinaction.run(shell_connection, max_end_time=self.max_end_time)
        self.assertEqual(shell_connection.raw_connection.linesep, 'testsep')

        self.assertIn('lava-test: # ', conn.prompt_str)
        self.assertIn('root@debian:~#', conn.prompt_str)

    def test_autologin_void_login_prompt(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        bootaction = [action for action in self.job.pipeline.actions if action.name == 'boot_image_retry'][0]
        autologinaction = [action for action in bootaction.internal_pipeline.actions if action.name == 'auto-login-action'][0]

        autologinaction.parameters.update({'auto_login': {'login_prompt': '',
                                                          'username': 'root'},
                                           'prompts': ['root@debian:~#']})

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, 'qemu-system-x86_64')

    def test_missing_autologin_void_prompts_list(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        bootaction = [action for action in self.job.pipeline.actions if action.name == 'boot_image_retry'][0]
        autologinaction = [action for action in bootaction.internal_pipeline.actions if action.name == 'auto-login-action'][0]

        autologinaction.parameters.update({'prompts': []})

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, 'qemu-system-x86_64')

    def test_missing_autologin_void_prompts_list_item(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        bootaction = [action for action in self.job.pipeline.actions if action.name == 'boot_image_retry'][0]
        autologinaction = [action for action in bootaction.internal_pipeline.actions if action.name == 'auto-login-action'][0]

        autologinaction.parameters.update({'prompts': ['']})

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, 'qemu-system-x86_64')

    def test_missing_autologin_void_prompts_list_item2(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        bootaction = [action for action in self.job.pipeline.actions if action.name == 'boot_image_retry'][0]
        autologinaction = [action for action in bootaction.internal_pipeline.actions if action.name == 'auto-login-action'][0]

        autologinaction.parameters.update({'prompts': ['root@debian:~#', '']})

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, 'qemu-system-x86_64')

    def test_missing_autologin_prompts_list(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        bootaction = [action for action in self.job.pipeline.actions if action.name == 'boot_image_retry'][0]
        autologinaction = [action for action in bootaction.internal_pipeline.actions if action.name == 'auto-login-action'][0]

        autologinaction.parameters.update({'prompts': ['root@debian:~#']})

        # initialise the first Connection object, a command line shell
        shell_connection = prepare_test_connection()

        # Test the AutoLoginAction directly
        conn = autologinaction.run(shell_connection, max_end_time=self.max_end_time)

        self.assertIn('lava-test: # ', conn.prompt_str)
        self.assertIn('root@debian:~#', conn.prompt_str)

    def test_missing_autologin_void_prompts_str(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        bootaction = [action for action in self.job.pipeline.actions if action.name == 'boot_image_retry'][0]
        autologinaction = [action for action in bootaction.internal_pipeline.actions if action.name == 'auto-login-action'][0]

        autologinaction.parameters.update({'prompts': ''})

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, 'qemu-system-x86_64')

    def test_missing_autologin_prompts_str(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        bootaction = [action for action in self.job.pipeline.actions if action.name == 'boot_image_retry'][0]
        autologinaction = [action for action in bootaction.internal_pipeline.actions if action.name == 'auto-login-action'][0]

        autologinaction.parameters.update({'prompts': ['root@debian:~#']})

        # initialise the first Connection object, a command line shell
        shell_connection = prepare_test_connection()

        # Test the AutoLoginAction directly
        conn = autologinaction.run(shell_connection, max_end_time=self.max_end_time)

        self.assertIn('lava-test: # ', conn.prompt_str)
        self.assertIn('root@debian:~#', conn.prompt_str)


class TestChecksum(StdoutTestCase):

    def setUp(self):
        super(TestChecksum, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-inline.yaml', mkdtemp())

    def test_download_checksum_match_success(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        deployimagesaction = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        downloadretryaction = [action for action in deployimagesaction.internal_pipeline.actions if action.name == 'download_retry'][0]
        httpdownloadaction = [action for action in downloadretryaction.internal_pipeline.actions if action.name == 'http_download'][0]

        # Just a small image
        httpdownloadaction.url = 'http://images.validation.linaro.org/unit-tests/rootfs.gz'
        httpdownloadaction.parameters.update({'images': {'rootfs': {
            'url': httpdownloadaction.url,
            'md5sum': '6ea432ac3c23210c816551782346ed1c',
            'sha256sum': '1a76b17701b9fdf6346b88eb49b0143a9c6912701b742a6e5826d6856edccd21'}}})
        httpdownloadaction.validate()
        httpdownloadaction.run(None, None)

    def test_download_checksum_match_fail(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        deployimagesaction = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        downloadretryaction = [action for action in deployimagesaction.internal_pipeline.actions if action.name == 'download_retry'][0]
        httpdownloadaction = [action for action in downloadretryaction.internal_pipeline.actions if action.name == 'http_download'][0]

        # Just a small image
        httpdownloadaction.url = 'http://images.validation.linaro.org/unit-tests/rootfs.gz'
        httpdownloadaction.parameters.update({'images': {'rootfs': {
            'url': httpdownloadaction.url,
            'md5sum': 'df1bd1598699e7a89d2e111111111111',
            'sha256sum': '92d6ff900d0c3656ab3f214ce6efd708f898fc5e259111111111111111111111'}}})
        httpdownloadaction.validate()

        self.assertRaises(JobError, httpdownloadaction.run, None, None)

    def test_download_no_images_no_checksum(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        deployimagesaction = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        downloadretryaction = [action for action in deployimagesaction.internal_pipeline.actions if action.name == 'download_retry'][0]
        httpdownloadaction = [action for action in downloadretryaction.internal_pipeline.actions if action.name == 'http_download'][0]

        # Just a small image
        httpdownloadaction.url = 'http://images.validation.linaro.org/unit-tests/rootfs.gz'
        del httpdownloadaction.parameters['images']
        httpdownloadaction.parameters.update({'rootfs': {'url': httpdownloadaction.url}})
        httpdownloadaction.validate()
        httpdownloadaction.run(None, None)

    def test_download_no_images_match_success(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        deployimagesaction = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        downloadretryaction = [action for action in deployimagesaction.internal_pipeline.actions if action.name == 'download_retry'][0]
        httpdownloadaction = [action for action in downloadretryaction.internal_pipeline.actions if action.name == 'http_download'][0]

        # Just a small image
        httpdownloadaction.url = 'http://images.validation.linaro.org/unit-tests/rootfs.gz'
        del httpdownloadaction.parameters['images']
        httpdownloadaction.parameters.update({
            'rootfs': {'url': httpdownloadaction.url,
                       'md5sum': '6ea432ac3c23210c816551782346ed1c',
                       'sha256sum': '1a76b17701b9fdf6346b88eb49b0143a9c6912701b742a6e5826d6856edccd21'}})
        httpdownloadaction.validate()
        httpdownloadaction.run(None, None)

    def test_download_no_images_match_fail(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        deployimagesaction = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        downloadretryaction = [action for action in deployimagesaction.internal_pipeline.actions if action.name == 'download_retry'][0]
        httpdownloadaction = [action for action in downloadretryaction.internal_pipeline.actions if action.name == 'http_download'][0]

        # Just a small image
        httpdownloadaction.url = 'http://images.validation.linaro.org/unit-tests/rootfs.gz'
        del httpdownloadaction.parameters['images']
        httpdownloadaction.parameters.update({
            'rootfs': {'url': httpdownloadaction.url,
                       'md5sum': '6ea432ac3c232122222221782346ed1c',
                       'sha256sum': '1a76b17701b9fdf63444444444444444446912701b742a6e5826d6856edccd21'}})
        httpdownloadaction.validate()
        self.assertRaises(JobError, httpdownloadaction.run, None, None)

    def test_no_test_action_validate(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        del self.job.pipeline.actions[2]

        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        except InfrastructureError as exc:
            check_missing_path(self, exc, 'qemu-system-x86_64')
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_uboot_checksum(self):
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        bbb_yaml = os.path.join(os.path.dirname(__file__), 'sample_jobs/bbb-ramdisk-nfs.yaml')
        with open(bbb_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "", output_dir='/tmp/')
        deploy = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        download = [action for action in deploy.internal_pipeline.actions if action.name == 'download_retry'][0]
        helper = [action for action in download.internal_pipeline.actions if action.name == 'file_download'][0]
        remote = helper.parameters[helper.key]
        md5sum = remote.get('md5sum', None)
        self.assertIsNone(md5sum)
        sha256sum = remote.get('sha256sum', None)
        self.assertIsNotNone(sha256sum)


class TestKvmGuest(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKvmGuest, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-local.yaml', mkdtemp())

    def test_guest_size(self):
        self.assertIn('guest', self.job.device['actions']['deploy']['methods']['image']['parameters'])
        self.assertEqual(512, self.job.device['actions']['deploy']['methods']['image']['parameters']['guest']['size'])


class TestKvmUefi(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKvmUefi, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-uefi.yaml', mkdtemp())

    @unittest.skipIf(infrastructure_error('qemu-system-x86_64'),
                     'qemu-system-x86_64 not installed')
    def test_uefi_path(self):
        deploy = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        downloaders = [action for action in deploy.internal_pipeline.actions if action.name == 'download_retry']
        self.assertEqual(len(downloaders), 2)
        uefi_download = downloaders[0]
        image_download = downloaders[1]
        self.assertEqual(image_download.key, 'disk1')
        uefi_dir = uefi_download.get_namespace_data(action='deployimages', label='image', key='uefi_dir')
        self.assertIsNotNone(uefi_dir)
        self.assertTrue(os.path.exists(uefi_dir))  # no download has taken place, but the directory needs to exist
        self.assertFalse(uefi_dir.endswith('bios-256k.bin'))
        boot = [action for action in self.job.pipeline.actions if action.name == 'boot_image_retry'][0]
        qemu = [action for action in boot.internal_pipeline.actions if action.name == 'boot_qemu_image'][0]
        execute = [action for action in qemu.internal_pipeline.actions if action.name == 'execute-qemu'][0]
        self.job.validate()
        self.assertIn('-L', execute.sub_command)
        self.assertIn(uefi_dir, execute.sub_command)


# class TestMonitor(StdoutTestCase):  # pylint: disable=too-many-public-methods
#
#     def setUp(self):
#         super(TestMonitor, self).setUp()
#         factory = Factory()
#         self.job = factory.create_kvm_job('sample_jobs/qemu-monitor.yaml', mkdtemp())
#
#     def test_qemu_monitor(self):
#         self.assertIsNotNone(self.job)
#         self.assertIsNotNone(self.job.pipeline)
#         self.assertIsNotNone(self.job.pipeline.actions)
#         self.job.validate()
