# Copyright (C) 2016 Linaro Limited
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
import yaml
from lava_dispatcher.pipeline.action import Pipeline, Timeout
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.test.test_basic import pipeline_reference, Factory, StdoutTestCase
from lava_dispatcher.pipeline.utils.strings import substitute


class InstallerFactory(Factory):  # pylint: disable=too-few-public-methods

    def create_qemu_installer_job(self, output_dir=None):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/kvm01.yaml'))
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/qemu-debian-installer.yaml')
        parser = JobParser()
        try:
            with open(sample_job_file) as sample_job_data:
                job = parser.parse(sample_job_data, device, 4212, None, "", output_dir=output_dir)
        except NotImplementedError:
            # some deployments listed in basics.yaml are not implemented yet
            return None
        return job


class TestIsoJob(StdoutTestCase):

    def setUp(self):
        factory = InstallerFactory()
        self.job = factory.create_qemu_installer_job(mkdtemp())
        self.assertIsNotNone(self.job)
        self.assertIsInstance(self.job, Job)
        self.assertIsInstance(self.job.pipeline, Pipeline)

    def test_job_reference(self):
        description_ref = pipeline_reference('qemu-debian-installer.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

    def test_iso_preparation(self):
        self.job.validate()
        deploy_iso = [action for action in self.job.pipeline.actions if action.name == 'deploy-iso-installer'][0]
        empty = [action for action in deploy_iso.internal_pipeline.actions
                 if action.name == 'prepare-empty-image'][0]
        self.assertEqual(empty.size, 2 * 1024 * 1024 * 1024)
        pull = [action for action in deploy_iso.internal_pipeline.actions if action.name == 'pull-installer-files'][0]
        self.assertEqual(pull.files['kernel'], '/install.amd/vmlinuz')
        self.assertEqual(pull.files['initrd'], '/install.amd/initrd.gz')
        self.assertEqual(len(pull.files.keys()), 2)

    def test_command_line(self):
        self.job.validate()
        deploy_iso = [action for action in self.job.pipeline.actions if action.name == 'deploy-iso-installer'][0]
        prepare = [action for action in deploy_iso.internal_pipeline.actions if action.name == 'prepare-qemu-commands'][0]
        self.assertEqual(prepare.boot_order, '-boot c')
        self.assertEqual(prepare.console, 'console=ttyS0,38400n8')
        self.assertIsNotNone(prepare.preseed_url)
        self.assertIn('-nographic', prepare.sub_command)
        self.assertIn(prepare.boot_order, prepare.sub_command)
        self.assertIn(' -drive format=raw,file={emptyimage} ', prepare.sub_command)
        self.assertIn('-append', prepare.command_line)
        self.assertIn('auto=true', prepare.command_line)
        self.assertIn('DEBIAN_FRONTEND=text', prepare.command_line)
        self.assertIn('{preseed} ---', prepare.command_line)
        self.assertIn('tftp://', prepare.command_line)
        self.assertIsNotNone(prepare.parameters['deployment_data']['prompts'])

    def test_substitutions(self):
        sub_command = [
            '/usr/bin/qemu-system-x86_64', '-nographic', '-enable-kvm',
            '-cpu host', '-net nic,model=virtio,macaddr=52:54:00:12:34:58 -net user',
            '-m 2048', ' -drive format=raw,file={emptyimage} ', '-boot c']
        substitutions = {'{emptyimage}': '/tmp/tmp.00000/hd.img'}
        sub_command = substitute(sub_command, substitutions)
        self.assertNotIn('{emptyimage}', sub_command)
        self.assertNotIn('/tmp/tmp.00000/hd.img', sub_command)
        self.assertIn('/tmp/tmp.00000/hd.img', ' '.join(sub_command))

    def test_timeout_inheritance(self):
        """
        test that classes pick up block timeouts

        Each action in the internal_pipeline needs to pick up the timeout
        specified in the job definition block for the top level parent action.
        """
        test_retry = [action for action in self.job.pipeline.actions if action.name == 'lava-test-retry'][0]
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/qemu-debian-installer.yaml')
        with open(sample_job_file, 'r') as jobdef:
            data = yaml.load(jobdef)
        testdata = [block['test'] for block in data['actions'] if 'test' in block][0]
        duration = (Timeout.parse(testdata['timeout']))
        self.assertEqual(
            duration,
            test_retry.timeout.duration
        )
        shell = [action for action in test_retry.internal_pipeline.actions if action.name == 'lava-test-shell'][0]
        self.assertEqual(
            duration,
            shell.timeout.duration
        )
        if shell.timeout.duration > shell.connection_timeout.duration:
            self.assertEqual(
                duration,
                shell.timeout.duration
            )
        else:
            self.fail("Incorrect timeout calculation")
