# Copyright (C) 2018 Linaro Limited
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

import unittest

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.tests.test_basic import Factory, StdoutTestCase
from lava_dispatcher.utils.shell import which


def check_docker():
    try:
        which("docker")
        return False
    except InfrastructureError:
        return True


def check_gdb_multipart():
    try:
        which("gdb-multiarch")
        return False
    except InfrastructureError:
        return True


class GDBFactory(Factory):
    def create_cc3230SF_job(self, filename):
        return self.create_job("cc3220SF-01.jinja2", filename)

    def create_cc3230SF_docker_job(self, filename):
        return self.create_job("cc3220SF-docker-01.jinja2", filename)


class TestGDB(StdoutTestCase):
    @unittest.skipIf(check_docker(), "docker not available")
    @unittest.skipIf(check_gdb_multipart(), "gdb-multiarch not available")
    def test_validate_errors(self):
        factory = GDBFactory()
        job = factory.create_cc3230SF_job("sample_jobs/cc3220SF-docker.yaml")
        with self.assertRaises(JobError):
            job.validate()
        self.assertEqual(
            job.pipeline.errors,
            ["Requesting a docker container while docker is not used for this device"],
        )

    @unittest.skipIf(check_docker(), "docker not available")
    @unittest.skipIf(check_gdb_multipart(), "gdb-multiarch not available")
    def test_without_docker(self):
        factory = GDBFactory()
        job = factory.create_cc3230SF_job("sample_jobs/cc3220SF.yaml")
        job.validate()
        description_ref = self.pipeline_reference("cc3220SF.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        # Check BootGDBRetry action
        action = job.pipeline.actions[1].pipeline.actions[0]
        self.assertEqual(action.name, "boot-gdb-retry")
        self.assertEqual(action.gdb, "gdb-multiarch")
        self.assertEqual(action.arguments, ["{ZEPHYR}"])
        self.assertEqual(len(action.commands), 4)
        self.assertEqual(
            action.commands[0],
            'target remote | openocd -c "gdb_port pipe" -f {OPENOCD_SCRIPT}',
        )
        self.assertEqual(action.commands[1], "monitor reset halt")
        self.assertEqual(action.commands[2], "load")
        self.assertEqual(action.commands[3], "set remotetimeout 10000")
        self.assertEqual(action.container, None)
        self.assertEqual(action.devices, [])

    @unittest.skipIf(check_docker(), "docker not available")
    @unittest.skipIf(check_gdb_multipart(), "gdb-multiarch not available")
    def test_with_docker(self):
        factory = GDBFactory()

        # Specify the docker container
        job = factory.create_cc3230SF_docker_job("sample_jobs/cc3220SF-docker.yaml")
        job.validate()
        description_ref = self.pipeline_reference("cc3220SF.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        # Check BootGDBRetry action
        action = job.pipeline.actions[1].pipeline.actions[0]
        self.assertEqual(action.name, "boot-gdb-retry")
        self.assertEqual(action.gdb, "gdb-multiarch")
        self.assertEqual(action.arguments, ["{ZEPHYR}"])
        self.assertEqual(len(action.commands), 4)
        self.assertEqual(
            action.commands[0],
            'target remote | openocd -c "gdb_port pipe" -f {OPENOCD_SCRIPT}',
        )
        self.assertEqual(action.commands[1], "monitor reset halt")
        self.assertEqual(action.commands[2], "load")
        self.assertEqual(action.commands[3], "set remotetimeout 10000")
        self.assertEqual(action.container, "ti-openocd-small")
        self.assertEqual(action.devices, ["/dev/hidraw3"])

        # use the default docker container
        job = factory.create_cc3230SF_docker_job("sample_jobs/cc3220SF.yaml")
        job.validate()
        description_ref = self.pipeline_reference("cc3220SF.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        # Check BootGDBRetry action
        action = job.pipeline.actions[1].pipeline.actions[0]
        self.assertEqual(action.name, "boot-gdb-retry")
        self.assertEqual(action.gdb, "gdb-multiarch")
        self.assertEqual(action.arguments, ["{ZEPHYR}"])
        self.assertEqual(len(action.commands), 4)
        self.assertEqual(
            action.commands[0],
            'target remote | openocd -c "gdb_port pipe" -f {OPENOCD_SCRIPT}',
        )
        self.assertEqual(action.commands[1], "monitor reset halt")
        self.assertEqual(action.commands[2], "load")
        self.assertEqual(action.commands[3], "set remotetimeout 10000")
        self.assertEqual(action.container, "ti-openocd")
        self.assertEqual(action.devices, ["/dev/hidraw3"])
