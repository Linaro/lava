# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
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
import shutil
import tempfile

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.actions.deploy.musca import (
    CheckMuscaFlashAction,
    DeployMuscaAutomationAction,
)
from lava_dispatcher.tests.test_basic import Factory, StdoutTestCase


class MuscaFactory(Factory):
    def create_musca_job(self, filename):
        return self.create_job("musca-01.jinja2", filename)


class TestMusca(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = MuscaFactory()
        self.job = self.factory.create_musca_job("sample_jobs/musca.yaml")
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.tmpdir)

    def test_musca_reference(self):
        self.job.validate()
        self.assertEqual([], self.job.pipeline.errors)
        description_ref = self.pipeline_reference("musca.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

    def test_musca_flash_fail_catch(self):
        flash_check_action = CheckMuscaFlashAction()
        flash_check_action.job = self.job
        flash_check_action.data = []
        flash_check_action.parameters = {"namespace": "test"}
        flash_check_action.set_namespace_data(
            action="mount-musca-usbmsd",
            label="musca-usb",
            key="mount-point",
            value=self.tmpdir,
        )
        self.assertEqual(None, flash_check_action.run(None, None))
        with open(os.path.join(self.tmpdir, "FAIL.TXT"), "w") as fail_file:
            fail_file.write("failed to flash software")
        with self.assertRaises(InfrastructureError):
            flash_check_action.run(None, None)

    def test_automation_action_places_file(self):
        automation_filename = "foo"
        automation_action = DeployMuscaAutomationAction(
            automation_filename=automation_filename
        )
        automation_action.job = self.job
        automation_action.data = []
        automation_action.parameters = {"namespace": "test"}
        automation_action.set_namespace_data(
            action="mount-musca-usbmsd",
            label="musca-usb",
            key="mount-point",
            value=self.tmpdir,
        )
        expected_path = os.path.join(self.tmpdir, automation_filename)
        # Check no file exists currently
        self.assertFalse(os.path.exists(expected_path))
        # Run the action
        automation_action.run(None, None)
        # Check file now exists
        self.assertTrue(os.path.exists(expected_path))
