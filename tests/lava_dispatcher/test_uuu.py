# Copyright 2019-2020 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
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
from unittest.mock import patch, MagicMock
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from lava_dispatcher.utils.uuu import OptionalContainerUuuAction
from lava_dispatcher.utils.containers import NullDriver, DockerDriver


class UUUBootFactory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_imx8mq_job(self, filename):
        return self.create_job("imx8mq-evk-01.jinja2", filename)


class TestUUUbootAction(StdoutTestCase):  # pylint: disable=too-many-public-methods
    def setUp(self):
        super().setUp()
        self.factory = UUUBootFactory()

    @patch(
        "lava_dispatcher.utils.uuu.OptionalContainerUuuAction.which",
        return_value="/bin/test_uuu",
    )
    def test_pipeline_uuu_only_uboot(self, which_mock):
        job = self.factory.create_imx8mq_job("sample_jobs/uuu-bootimage-only.yaml")
        self.assertIsNotNone(job)

        # Test that generated pipeline is the same as defined in pipeline_refs
        description_ref = self.pipeline_reference("uuu-bootimage-only.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())


class TestUUUActionDriver(unittest.TestCase):
    def create_action(self, uuu_device_parameters):
        action = OptionalContainerUuuAction()
        action.job = MagicMock()
        action.job.device = {
            "actions": {
                "boot": {"methods": {"uuu": {"options": uuu_device_parameters}}}
            }
        }
        return action

    def test_uuu_null_driver(self):
        uuu_device_parameters = {"docker_image": "", "remote_options": ""}
        action = self.create_action(uuu_device_parameters)
        self.assertIsInstance(action.driver, NullDriver)

    def test_uuu_docker_driver(self):
        uuu_device_parameters = {
            "docker_image": "atline/uuu:1.3.191",
            "remote_options": "",
        }
        action = self.create_action(uuu_device_parameters)
        self.assertIsInstance(action.driver, DockerDriver)

    @patch("lava_dispatcher.actions.boot.uuu.OptionalContainerUuuAction.run_cmd")
    def test_native_uuu_cmd(self, mock_cmd):
        uuu_device_parameters = {"docker_image": "", "remote_options": ""}
        action = self.create_action(uuu_device_parameters)
        action.run_uuu(["foo", "bar"])
        mock_cmd.assert_called_with(["foo", "bar"], False, None, None)

    @patch("lava_dispatcher.actions.boot.uuu.OptionalContainerUuuAction.run_cmd")
    def test_docker_uuu_local_cmd(self, mock_cmd):
        uuu_device_parameters = {
            "docker_image": "atline/uuu:1.3.191",
            "remote_options": "",
        }
        action = self.create_action(uuu_device_parameters)
        action.run_uuu(["foo", "bar"])
        mock_cmd.assert_called_with(
            [
                "docker",
                "run",
                "--rm",
                "--init",
                "--privileged",
                "--volume=/dev:/dev",
                "--net=host",
                "atline/uuu:1.3.191",
                "foo",
                "bar",
            ],
            False,
            None,
            None,
        )

    @patch("lava_dispatcher.utils.uuu.dispatcher_ip", return_value="foo")
    @patch(
        "lava_dispatcher.actions.boot.uuu.OptionalContainerUuuAction.get_namespace_data",
        return_value="bar",
    )
    @patch("lava_dispatcher.actions.boot.uuu.OptionalContainerUuuAction.run_cmd")
    def test_docker_uuu_remote_cmd(self, mock_cmd, mock_location, mock_ip):
        uuu_device_parameters = {
            "docker_image": "atline/uuu:1.3.191",
            "remote_options": "--tlsverify --tlscacert=/labScripts/remote_cert/ca.pem --tlscert=/labScripts/remote_cert/cert.pem --tlskey=/labScripts/remote_cert/key.pem -H 10.192.244.5:2376",
        }
        action = self.create_action(uuu_device_parameters)
        action.run_uuu(["foo", "bar"])
        mock_cmd.assert_called_with(
            [
                "docker",
                "--tlsverify",
                "--tlscacert=/labScripts/remote_cert/ca.pem",
                "--tlscert=/labScripts/remote_cert/cert.pem",
                "--tlskey=/labScripts/remote_cert/key.pem",
                "-H",
                "10.192.244.5:2376",
                "run",
                "--rm",
                "--init",
                "--privileged",
                "--volume=/dev:/dev",
                "--net=host",
                "atline/uuu:1.3.191",
                "bash",
                "-c",
                "mkdir -p bar && mount -t nfs -o nolock foo:bar bar && foo bar",
            ],
            False,
            None,
            None,
        )
