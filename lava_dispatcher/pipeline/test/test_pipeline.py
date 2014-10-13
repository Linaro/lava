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

# This file is to be extended to make a clean testbed for checking
# the memory usage of the pipeline code and spotting leaks.

import unittest


class Job(object):
    pass


class TestJob(unittest.TestCase):  # pylint: disable=too-many-public-methods

    class FakeJob(object):

        def __init__(self, parameters):
            super(TestJob.FakeJob, self).__init__()
            self.parameters = parameters

    def setUp(self):
        self.parameters = {
            "job_name": "fakejob",
            'output_dir': ".",
            "actions": [
                {
                    'deploy': {
                        'failure_retry': 3
                    },
                    'boot': {
                        'failure_retry': 4
                    },
                    'test': {
                        'failure_retry': 5
                    }
                }
            ]
        }
        self.fakejob = TestAction.FakeJob(self.parameters)


class TestAction(unittest.TestCase):

    def test_references_a_device(self):
        device = object()
        from meliae import scanner
        scanner.dump_all_objects('filename.json')
