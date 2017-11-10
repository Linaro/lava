# Copyright (C) 2017 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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
import unittest
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.utils.filesystem import mkdtemp
from lava_dispatcher.action import JobError
from lava_dispatcher.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.utils.shell import infrastructure_error_multi_paths


class DownloadFactory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_download_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/db410c-01.yaml'))
        download_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(download_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "",
                               output_dir=output_dir)
        return job


class TestDownloadDeploy(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDownloadDeploy, self).setUp()
        self.factory = DownloadFactory()
        self.job = self.factory.create_download_job('sample_jobs/download.yaml',
                                                    mkdtemp())

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        self.assertIsInstance(self.job.device['device_info'], list)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = self.pipeline_reference('download.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

    @unittest.skipIf(infrastructure_error_multi_paths(
        ['lxc-info', 'img2simg', 'simg2img']),
        "lxc or img2simg or simg2img not installed")
    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)
