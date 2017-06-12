# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

from lava_dispatcher.pipeline.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp


class TestCommand(StdoutTestCase):

    def setUp(self):
        super(TestCommand, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-command.yaml', mkdtemp())

    def test_pipeline(self):
        description_ref = self.pipeline_reference('kvm-command.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

        command = [action for action in self.job.pipeline.actions if action.name == 'user-command'][0]
        self.assertEqual(command.parameters['name'], 'user_command_to_run')
        self.assertEqual(command.timeout.duration, 60)
