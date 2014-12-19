# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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
import logging
import glob
import unittest
import yaml

from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.action import Pipeline, Action, RetryAction, JobError
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.pipeline.actions.deploy.download import (
    DownloaderAction,
    DownloadHandler,
    FileDownloadAction,
    HttpDownloadAction,
)
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.log import YamlLogger
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import ApplyOverlayImage
from lava_dispatcher.pipeline.actions.deploy.image import QCowConversionAction
from lava_dispatcher.pipeline.actions.deploy.mount import (
    MountAction,
    LoopCheckAction,
    LoopMountAction,
    UnmountAction,
    OffsetAction
)
from lava_dispatcher.pipeline.actions.deploy.overlay import (
    CompressOverlay,
    CustomisationAction,
    MultinodeOverlayAction,
    OverlayAction,
    TestDefinitionAction,
)
from lava_dispatcher.pipeline.actions.deploy.testdef import (
    InlineRepoAction,
)
from lava_dispatcher.pipeline.actions.boot.kvm import BootAction


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
        # a formal submit action would include an internal pipe to handle
        # the XMLRPC, including possible failure states and retries.
        action = Action()
        action.name = "submit"
        action.description = "submit results"
        action.summary = "submit"
        action.job = job
        pipe.add_action(action)
        self.assertEqual(action.level, "4")
        self.assertEqual(len(pipe.describe().values()), 8)
        # uncomment to see the YAML dump of the pipeline.
        # print yaml.dump(pipe.describe())


class TestKVMBasicDeploy(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKVMBasicDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm.yaml', mkdtemp())

    def test_deploy_job(self):
        # from meliae import scanner
        # scanner.dump_all_objects('/tmp/lava-unittest.json')
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_kvm_basic_deploy(self):  # pylint: disable=too-many-statements
        self.assertEqual(len(self.job.pipeline.describe().values()), 32)  # this will keep changing until KVM is complete.
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(len(action.pipeline.children[action.pipeline]), 6)
                # check parser has created a suitable deployment
                download_retry = action.pipeline.children[action.pipeline][0]
                self.assertIsInstance(download_retry, DownloaderAction)
                self.assertIsInstance(download_retry, RetryAction)
                self.assertEqual(len(download_retry.pipeline.children), 1)
                self.assertIsInstance(download_retry.log_handler, logging.FileHandler)
                self.assertIsInstance(download_retry.logger, YamlLogger)

                download = download_retry.pipeline.children[download_retry.pipeline][0]
                self.assertEqual(download.name, "http_download")
                self.assertIsInstance(download, DownloadHandler)
                self.assertIsInstance(download, HttpDownloadAction)
                self.assertIsInstance(download.log_handler, logging.FileHandler)
                self.assertIsInstance(download.logger, YamlLogger)

                mount = action.pipeline.children[action.pipeline][1]
                self.assertIsInstance(mount.internal_pipeline, Pipeline)
                self.assertEqual(mount.name, "mount_action")
                self.assertIsInstance(mount, MountAction)
                self.assertIsInstance(mount.log_handler, logging.FileHandler)
                self.assertIsInstance(mount.logger, YamlLogger)

                # Check internal Mount pipeline
                self.assertEqual(len(mount.internal_pipeline.actions), 3)
                offset = mount.internal_pipeline.actions[0]
                self.assertEqual(offset.name, "offset_action")
                self.assertIsInstance(offset, OffsetAction)
                self.assertIsInstance(offset.log_handler, logging.FileHandler)
                self.assertIsInstance(offset.logger, YamlLogger)

                loop_check = mount.internal_pipeline.actions[1]
                self.assertEqual(loop_check.name, "loop_check")
                self.assertIsInstance(loop_check, LoopCheckAction)
                self.assertIsInstance(loop_check.log_handler, logging.FileHandler)
                self.assertIsInstance(loop_check.logger, YamlLogger)

                loop_mount = mount.internal_pipeline.actions[2]
                self.assertEqual(loop_mount.name, "loop_mount")
                self.assertIsInstance(loop_mount, LoopMountAction)
                self.assertIsInstance(loop_mount, RetryAction)
                self.assertIsInstance(loop_mount.log_handler, logging.FileHandler)
                self.assertIsInstance(loop_mount.logger, YamlLogger)

                customise = action.pipeline.children[action.pipeline][2]
                self.assertEqual(customise.name, "customise")
                self.assertIsInstance(customise, CustomisationAction)
                self.assertIsInstance(customise.log_handler, logging.FileHandler)
                self.assertIsInstance(customise.logger, YamlLogger)

                overlay = action.pipeline.children[action.pipeline][3]
                self.assertEqual(overlay.name, "lava-overlay")
                self.assertIsInstance(overlay, OverlayAction)
                self.assertIsInstance(overlay.log_handler, logging.FileHandler)
                self.assertIsInstance(overlay.logger, YamlLogger)

                apply_overlay = action.pipeline.children[action.pipeline][4]
                self.assertEqual(apply_overlay.name, "apply-overlay-image")
                self.assertIsInstance(apply_overlay, ApplyOverlayImage)
                self.assertIsInstance(apply_overlay.log_handler, logging.FileHandler)
                self.assertIsInstance(apply_overlay.logger, YamlLogger)

                unmount = action.pipeline.children[action.pipeline][5]
                self.assertEqual(unmount.name, "umount-retry")
                self.assertIsInstance(unmount, UnmountAction)
                self.assertIsInstance(unmount, RetryAction)
                self.assertIsInstance(unmount.log_handler, logging.FileHandler)
                self.assertIsInstance(unmount.logger, YamlLogger)

                # ensure the test definition action is inside the mount pipeline
                self.assertIsInstance(overlay.internal_pipeline.actions[1], TestDefinitionAction)

            elif isinstance(action, Action):
                pass
            else:
                # print action
                self.fail("No deploy action found")

    def test_kvm_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            if action.errors:
                # python3
                print(action.errors)  # pylint: disable=superfluous-parens
            self.assertTrue(action.valid)

    def test_download_actions(self):
        """
        Once the download module is converted to requests and
        individual actions, complete this placeholder
        """
        pass

    def test_kvm_basic_mount(self):
        mount = None
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                # check parser has created a suitable deployment
                mount = action.pipeline.children[action.pipeline][1]
                self.assertIsInstance(mount.internal_pipeline, Pipeline)
                self.assertIsInstance(mount, MountAction)
                customise = action.pipeline.children[action.pipeline][2]
                self.assertIsInstance(customise, CustomisationAction)
                apply_overlay = action.pipeline.children[action.pipeline][4]
                self.assertIsInstance(apply_overlay, ApplyOverlayImage)
                overlay = action.pipeline.children[action.pipeline][3]
                self.assertIsInstance(overlay, OverlayAction)
                unmount = action.pipeline.children[action.pipeline][5]
                self.assertIsInstance(unmount, UnmountAction)
        self.assertTrue(mount.valid)
        self.assertEqual(len(mount.internal_pipeline.actions), 3)
        self.assertIsInstance(mount.internal_pipeline.actions[0], OffsetAction)
        self.assertIsInstance(mount.internal_pipeline.actions[1], LoopCheckAction)
        self.assertIsInstance(mount.internal_pipeline.actions[2], LoopMountAction)

    def test_kvm_basic_overlay(self):
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

    def test_kvm_basic_boot(self):
        for action in self.job.pipeline.actions:
            if isinstance(action, BootAction):
                # get the action & populate it
                self.assertEqual(action.parameters['method'], 'qemu')

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


class TestKVMQcow2Deploy(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKVMQcow2Deploy, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-qcow2.yaml', mkdtemp())

    def test_deploy_job(self):
        # from meliae import scanner
        # scanner.dump_all_objects('/tmp/lava-unittest.json')
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_kvm_basic_deploy(self):  # pylint: disable=too-many-statements
        self.assertEqual(len(self.job.pipeline.describe().values()), 33)  # this will keep changing until KVM is complete.
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(len(action.pipeline.children[action.pipeline]), 7)
                # check parser has created a suitable deployment
                download_retry = action.pipeline.children[action.pipeline][0]
                self.assertIsInstance(download_retry, DownloaderAction)
                self.assertIsInstance(download_retry, RetryAction)
                self.assertEqual(len(download_retry.pipeline.children), 1)
                self.assertIsInstance(download_retry.log_handler, logging.FileHandler)
                self.assertIsInstance(download_retry.logger, YamlLogger)

                download = download_retry.pipeline.children[download_retry.pipeline][0]
                self.assertEqual(download.name, "http_download")
                self.assertIsInstance(download, DownloadHandler)
                self.assertIsInstance(download, HttpDownloadAction)
                self.assertIsInstance(download.log_handler, logging.FileHandler)
                self.assertIsInstance(download.logger, YamlLogger)

                convert = action.pipeline.children[action.pipeline][1]
                self.assertEqual(convert.name, "qcow2_convert")
                self.assertIsInstance(convert, QCowConversionAction)
                self.assertIsInstance(convert.log_handler, logging.FileHandler)
                self.assertIsInstance(convert.logger, YamlLogger)

                mount = action.pipeline.children[action.pipeline][2]
                self.assertIsInstance(mount.internal_pipeline, Pipeline)
                self.assertEqual(mount.name, "mount_action")
                self.assertIsInstance(mount, MountAction)
                self.assertIsInstance(mount.log_handler, logging.FileHandler)
                self.assertIsInstance(mount.logger, YamlLogger)

                # Check internal Mount pipeline
                self.assertEqual(len(mount.internal_pipeline.actions), 3)
                offset = mount.internal_pipeline.actions[0]
                self.assertEqual(offset.name, "offset_action")
                self.assertIsInstance(offset, OffsetAction)
                self.assertIsInstance(offset.log_handler, logging.FileHandler)
                self.assertIsInstance(offset.logger, YamlLogger)

                loop_check = mount.internal_pipeline.actions[1]
                self.assertEqual(loop_check.name, "loop_check")
                self.assertIsInstance(loop_check, LoopCheckAction)
                self.assertIsInstance(loop_check.log_handler, logging.FileHandler)
                self.assertIsInstance(loop_check.logger, YamlLogger)

                loop_mount = mount.internal_pipeline.actions[2]
                self.assertEqual(loop_mount.name, "loop_mount")
                self.assertIsInstance(loop_mount, LoopMountAction)
                self.assertIsInstance(loop_mount, RetryAction)
                self.assertIsInstance(loop_mount.log_handler, logging.FileHandler)
                self.assertIsInstance(loop_mount.logger, YamlLogger)

                customise = action.pipeline.children[action.pipeline][3]
                self.assertEqual(customise.name, "customise")
                self.assertIsInstance(customise, CustomisationAction)
                self.assertIsInstance(customise.log_handler, logging.FileHandler)
                self.assertIsInstance(customise.logger, YamlLogger)

                overlay = action.pipeline.children[action.pipeline][4]
                self.assertEqual(overlay.name, "lava-overlay")
                self.assertIsInstance(overlay, OverlayAction)
                self.assertIsInstance(overlay.log_handler, logging.FileHandler)
                self.assertIsInstance(overlay.logger, YamlLogger)

                apply_overlay = action.pipeline.children[action.pipeline][5]
                self.assertEqual(apply_overlay.name, "apply-overlay-image")
                self.assertIsInstance(apply_overlay, ApplyOverlayImage)
                self.assertIsInstance(apply_overlay.log_handler, logging.FileHandler)
                self.assertIsInstance(apply_overlay.logger, YamlLogger)
                self.assertEqual(
                    apply_overlay.timeout.duration,
                    self.job.device.overrides['timeouts'][apply_overlay.name]
                )

                unmount = action.pipeline.children[action.pipeline][6]
                self.assertEqual(unmount.name, "umount-retry")
                self.assertIsInstance(unmount, UnmountAction)
                self.assertIsInstance(unmount, RetryAction)
                self.assertIsInstance(unmount.log_handler, logging.FileHandler)
                self.assertIsInstance(unmount.logger, YamlLogger)

                # ensure the test definition action is inside the mount pipeline
                self.assertIsInstance(overlay.internal_pipeline.actions[1], TestDefinitionAction)

            elif isinstance(action, Action):
                pass
            else:
                # print action
                self.fail("No deploy action found")

    def test_kvm_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            if action.errors:
                # python3
                print(action.errors)  # pylint: disable=superfluous-parens
            self.assertTrue(action.valid)


class TestKVMDownloadLocalDeploy(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKVMDownloadLocalDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-local.yaml', mkdtemp())

    def test_deploy_job(self):
        # from meliae import scanner
        # scanner.dump_all_objects('/tmp/lava-unittest.json')
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_kvm_basic_deploy(self):  # pylint: disable=too-many-statements
        self.assertEqual(len(self.job.pipeline.describe().values()), 32)  # this will keep changing until KVM is complete.
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(len(action.pipeline.children[action.pipeline]), 6)
                # check parser has created a suitable deployment
                download_retry = action.pipeline.children[action.pipeline][0]
                self.assertIsInstance(download_retry, DownloaderAction)
                self.assertIsInstance(download_retry, RetryAction)
                self.assertEqual(len(download_retry.pipeline.children), 1)
                self.assertIsInstance(download_retry.log_handler, logging.FileHandler)
                self.assertIsInstance(download_retry.logger, YamlLogger)

                download = download_retry.pipeline.children[download_retry.pipeline][0]
                self.assertEqual(download.name, "file_download")
                self.assertIsInstance(download, DownloadHandler)
                self.assertIsInstance(download, FileDownloadAction)
                self.assertIsInstance(download.log_handler, logging.FileHandler)
                self.assertIsInstance(download.logger, YamlLogger)

                mount = action.pipeline.children[action.pipeline][1]
                self.assertIsInstance(mount.internal_pipeline, Pipeline)
                self.assertEqual(mount.name, "mount_action")
                self.assertIsInstance(mount, MountAction)
                self.assertIsInstance(mount.log_handler, logging.FileHandler)
                self.assertIsInstance(mount.logger, YamlLogger)

                # Check internal Mount pipeline
                self.assertEqual(len(mount.internal_pipeline.actions), 3)
                offset = mount.internal_pipeline.actions[0]
                self.assertEqual(offset.name, "offset_action")
                self.assertIsInstance(offset, OffsetAction)
                self.assertIsInstance(offset.log_handler, logging.FileHandler)
                self.assertIsInstance(offset.logger, YamlLogger)

                loop_check = mount.internal_pipeline.actions[1]
                self.assertEqual(loop_check.name, "loop_check")
                self.assertIsInstance(loop_check, LoopCheckAction)
                self.assertIsInstance(loop_check.log_handler, logging.FileHandler)
                self.assertIsInstance(loop_check.logger, YamlLogger)

                loop_mount = mount.internal_pipeline.actions[2]
                self.assertEqual(loop_mount.name, "loop_mount")
                self.assertIsInstance(loop_mount, LoopMountAction)
                self.assertIsInstance(loop_mount, RetryAction)
                self.assertIsInstance(loop_mount.log_handler, logging.FileHandler)
                self.assertIsInstance(loop_mount.logger, YamlLogger)

                customise = action.pipeline.children[action.pipeline][2]
                self.assertEqual(customise.name, "customise")
                self.assertIsInstance(customise, CustomisationAction)
                self.assertIsInstance(customise.log_handler, logging.FileHandler)
                self.assertIsInstance(customise.logger, YamlLogger)

                overlay = action.pipeline.children[action.pipeline][3]
                self.assertEqual(overlay.name, "lava-overlay")
                self.assertIsInstance(overlay, OverlayAction)
                self.assertIsInstance(overlay.log_handler, logging.FileHandler)
                self.assertIsInstance(overlay.logger, YamlLogger)

                apply_overlay = action.pipeline.children[action.pipeline][4]
                self.assertEqual(apply_overlay.name, "apply-overlay-image")
                self.assertIsInstance(apply_overlay, ApplyOverlayImage)
                self.assertIsInstance(apply_overlay.log_handler, logging.FileHandler)
                self.assertIsInstance(apply_overlay.logger, YamlLogger)

                unmount = action.pipeline.children[action.pipeline][5]
                self.assertEqual(unmount.name, "umount-retry")
                self.assertIsInstance(unmount, UnmountAction)
                self.assertIsInstance(unmount, RetryAction)
                self.assertIsInstance(unmount.log_handler, logging.FileHandler)
                self.assertIsInstance(unmount.logger, YamlLogger)

            elif isinstance(action, Action):
                pass
            else:
                # print action
                self.fail("No deploy action found")


class TestKVMInlineTestDeploy(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestKVMInlineTestDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-inline.yaml', mkdtemp())

    def test_kvm_inline_deploy(self):  # pylint: disable=too-many-statements,too-many-locals
        self.assertEqual(len(self.job.pipeline.describe().values()), 28)  # this will keep changing until KVM is complete.
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(len(action.pipeline.children[action.pipeline]), 6)
                # check parser has created a suitable deployment
                download_retry = action.pipeline.children[action.pipeline][0]
                self.assertIsInstance(download_retry, DownloaderAction)
                self.assertIsInstance(download_retry, RetryAction)
                self.assertEqual(len(download_retry.pipeline.children), 1)
                self.assertIsInstance(download_retry.log_handler, logging.FileHandler)
                self.assertIsInstance(download_retry.logger, YamlLogger)

                download = download_retry.pipeline.children[download_retry.pipeline][0]
                self.assertEqual(download.name, "http_download")
                self.assertIsInstance(download, DownloadHandler)
                self.assertIsInstance(download, HttpDownloadAction)
                self.assertIsInstance(download.log_handler, logging.FileHandler)
                self.assertIsInstance(download.logger, YamlLogger)

                mount = action.pipeline.children[action.pipeline][1]
                self.assertIsInstance(mount.internal_pipeline, Pipeline)
                self.assertEqual(mount.name, "mount_action")
                self.assertIsInstance(mount, MountAction)
                self.assertIsInstance(mount.log_handler, logging.FileHandler)
                self.assertIsInstance(mount.logger, YamlLogger)

                # Check internal Mount pipeline
                self.assertEqual(len(mount.internal_pipeline.actions), 3)
                offset = mount.internal_pipeline.actions[0]
                self.assertEqual(offset.name, "offset_action")
                self.assertIsInstance(offset, OffsetAction)
                self.assertIsInstance(offset.log_handler, logging.FileHandler)
                self.assertIsInstance(offset.logger, YamlLogger)

                loop_check = mount.internal_pipeline.actions[1]
                self.assertEqual(loop_check.name, "loop_check")
                self.assertIsInstance(loop_check, LoopCheckAction)
                self.assertIsInstance(loop_check.log_handler, logging.FileHandler)
                self.assertIsInstance(loop_check.logger, YamlLogger)

                loop_mount = mount.internal_pipeline.actions[2]
                self.assertEqual(loop_mount.name, "loop_mount")
                self.assertIsInstance(loop_mount, LoopMountAction)
                self.assertIsInstance(loop_mount, RetryAction)
                self.assertIsInstance(loop_mount.log_handler, logging.FileHandler)
                self.assertIsInstance(loop_mount.logger, YamlLogger)

                customise = action.pipeline.children[action.pipeline][2]
                self.assertEqual(customise.name, "customise")
                self.assertIsInstance(customise, CustomisationAction)
                self.assertIsInstance(customise.log_handler, logging.FileHandler)
                self.assertIsInstance(customise.logger, YamlLogger)

                overlay = action.pipeline.children[action.pipeline][3]
                self.assertEqual(overlay.name, "lava-overlay")
                self.assertIsInstance(overlay, OverlayAction)
                self.assertIsInstance(overlay.log_handler, logging.FileHandler)
                self.assertIsInstance(overlay.logger, YamlLogger)

                # Check internal Overlay pipeline
                self.assertEqual(len(overlay.internal_pipeline.actions), 3)
                multi_overlay = overlay.internal_pipeline.actions[0]
                self.assertEqual(multi_overlay.name, "lava-multinode-overlay")
                self.assertIsInstance(multi_overlay, MultinodeOverlayAction)

                testdef = overlay.internal_pipeline.actions[1]
                self.assertEqual(testdef.name, "test-definition")
                self.assertIsInstance(testdef, TestDefinitionAction)

                # Check internal pipeline
                self.assertEqual(len(testdef.internal_pipeline.actions), 4)
                inline_repo = testdef.internal_pipeline.actions[0]
                self.assertEqual(inline_repo.name, "inline-repo-action")
                self.assertIsInstance(inline_repo, InlineRepoAction)

                compress_overlay = overlay.internal_pipeline.actions[2]
                self.assertEqual(compress_overlay.name, "compress-overlay")
                self.assertIsInstance(compress_overlay, CompressOverlay)

                apply_overlay = action.pipeline.children[action.pipeline][4]
                self.assertEqual(apply_overlay.name, "apply-overlay-image")
                self.assertIsInstance(apply_overlay, ApplyOverlayImage)
                self.assertIsInstance(apply_overlay.log_handler, logging.FileHandler)
                self.assertIsInstance(apply_overlay.logger, YamlLogger)

                unmount = action.pipeline.children[action.pipeline][5]
                self.assertEqual(unmount.name, "umount-retry")
                self.assertIsInstance(unmount, UnmountAction)
                self.assertIsInstance(unmount, RetryAction)
                self.assertIsInstance(unmount.log_handler, logging.FileHandler)
                self.assertIsInstance(unmount.logger, YamlLogger)

            elif isinstance(action, Action):
                pass
            else:
                # print action
                self.fail("No deploy action found")

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
