# Copyright 2026 Qualcomm Inc.
#
# Author: Milosz Wasilewski <milosz.wasilewski@oss.qualcomm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import patch

from voluptuous import Invalid

from lava_common.exceptions import ConfigurationError, JobError
from lava_dispatcher.actions.boot.qdl import FlashQDLAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestQDLBootAction(LavaDispatcherTestCase):
    @patch("lava_dispatcher.action.Action.parsed_command")
    @patch("lava_dispatcher.actions.boot.qdl.which")
    def test_qdl_job(self, which_mock, parsed_mock):
        which_mock.return_value = "/foo/qdl"
        parsed_mock.return_value = "qdl version v2.7"
        job = Factory().create_job("qcs6490-rb3gen2", "sample_jobs/qdl-boot.yaml")
        job.device.update({"board_qdl_id": "abcdef12"})
        job.device.update({"board_id": "abcdef12"})
        self.assertEqual(len(job.pipeline.actions), 4)
        job.validate()
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        description_ref = self.pipeline_reference("qdl.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    @patch("lava_dispatcher.action.Action.parsed_command")
    @patch("lava_dispatcher.actions.boot.qdl.which")
    def test_qdl_job_empty_rootfs(self, which_mock, parsed_mock):
        which_mock.return_value = "/foo/qdl"
        parsed_mock.return_value = "qdl version v2.7"
        job = Factory().create_job(
            "qcs6490-rb3gen2", "sample_jobs/qdl-boot-empty-rootfs.yaml"
        )
        job.device.update({"board_qdl_id": "abcdef12"})
        job.device.update({"board_id": "abcdef12"})
        self.assertEqual(len(job.pipeline.actions), 5)
        with self.assertRaises(JobError):
            job.validate()

    @patch("lava_dispatcher.actions.boot.qdl.which")
    def test_qdl_job_no_qdl(self, which_mock):
        which_mock.return_value = ""
        job = Factory().create_job("qcs6490-rb3gen2", "sample_jobs/qdl-boot.yaml")
        job.device.update({"board_qdl_id": "abcdef12"})
        job.device.update({"board_id": "abcdef12"})
        self.assertEqual(len(job.pipeline.actions), 4)
        with self.assertRaises(ConfigurationError):
            job.validate()

    def test_qdl_job_qdl_1(self):
        self.assert_version_too_low("qdl version v1.0", "1.0")

    def validate_qdl_job(self, version_output, **parameters):
        """
        Create and validate a qdl job with "qdl --version" reporting
        version_output, adding parameters to the qdl boot action. Returns the
        validated job.
        """

        def add_parameters(job_dict):
            for action in job_dict["actions"]:
                if action.get("boot", {}).get("method") == "qdl":
                    action["boot"].update(parameters)

        with (
            patch("lava_dispatcher.actions.boot.qdl.which") as which_mock,
            patch("lava_dispatcher.action.Action.parsed_command") as parsed_mock,
        ):
            which_mock.return_value = "/foo/qdl"
            parsed_mock.return_value = version_output
            job = Factory().create_job(
                "qcs6490-rb3gen2",
                "sample_jobs/qdl-boot.yaml",
                job_dict_preprocessor=add_parameters,
            )
            job.device.update({"board_qdl_id": "abcdef12"})
            job.device.update({"board_id": "abcdef12"})
            self.assertEqual(len(job.pipeline.actions), 4)
            job.validate()
            return job

    def assert_skipblock(self, version_output, supported):
        """
        Assert that "skipblock: true" passes --skipblock=sha256 to qdl when
        the "qdl --version" output is 2.7 or higher, and is rejected otherwise.
        """
        if supported:
            job = self.validate_qdl_job(version_output, skipblock=True)
            action = job.pipeline.find_action(FlashQDLAction)
            self.assertIn("--skipblock=sha256", action.base_command)
        else:
            with self.assertRaises(JobError) as exc:
                self.validate_qdl_job(version_output, skipblock=True)
            self.assertIn("skipblock requires qdl 2.7 or higher", str(exc.exception))

    def test_qdl_skipblock_off_by_default(self):
        job = self.validate_qdl_job("qdl version v2.7")
        action = job.pipeline.find_action(FlashQDLAction)
        self.assertNotIn("--skipblock=sha256", action.base_command)

    def test_qdl_skipblock_disabled(self):
        job = self.validate_qdl_job("qdl version v2.7", skipblock=False)
        action = job.pipeline.find_action(FlashQDLAction)
        self.assertNotIn("--skipblock=sha256", action.base_command)

    def test_qdl_skipblock_must_be_a_bool(self):
        with self.assertRaises(Invalid):
            self.validate_qdl_job("qdl version v2.7", skipblock="sha256")

    def assert_version_too_low(self, version_output, version):
        with self.assertRaises(ConfigurationError) as exc:
            self.validate_qdl_job(version_output)
        self.assertEqual(
            f"qdl version {version} is too low, 2.0 or higher is required",
            str(exc.exception),
        )

    def assert_version_unparsable(self, version_output):
        with self.assertRaises(ConfigurationError) as exc:
            self.validate_qdl_job(version_output)
        self.assertEqual(
            "Unable to parse the version of qdl at /foo/qdl", str(exc.exception)
        )

    def test_qdl_version_from_git_tag(self):
        # built from a git tag, the version is prefixed with "v"
        for version_output, skipblock in (
            ("qdl version v2.0", False),
            ("qdl version v2.6", False),
            ("qdl version v2.7", True),
            ("qdl version v2.8", True),
            # compared as numbers, not as strings
            ("qdl version v2.10", True),
            ("qdl version v3.0", True),
            ("qdl version v10.0", True),
        ):
            with self.subTest(version_output=version_output):
                self.assert_skipblock(version_output, skipblock)

    def test_qdl_version_from_debian_package(self):
        # installed from a Debian package, the version reported is the package
        # version: [epoch:]upstream_version[-debian_revision]
        for version_output, skipblock in (
            ("qdl version 2.0-1", False),
            ("qdl version 2.6-1~bpo13+1", False),
            ("qdl version 2.6.9-1", False),
            ("qdl version 2.7-1~bpo13+1", True),
            ("qdl version 2.7-1", True),
            ("qdl version 2.7.1-1+deb13u1", True),
            ("qdl version 1:2.7+dfsg-2", True),
            ("qdl version 3.0-1~bpo13+1", True),
            ("qdl version 1:3.0-1", True),
            # a Debian package built from a git tag keeps the "v" prefix
            ("qdl version v2.7-1~bpo13+1", True),
        ):
            with self.subTest(version_output=version_output):
                self.assert_skipblock(version_output, skipblock)

    def test_qdl_version_surrounded_by_other_output(self):
        for version_output in (
            "  qdl version v2.7  \n",
            "text before version\nqdl version v2.7\n",
            "qdl version v2.7\ntext after version\n",
            "text before version\nqdl version v2.7\ntext after version",
        ):
            with self.subTest(version_output=version_output):
                self.assert_skipblock(version_output, True)

    def test_qdl_version_too_low(self):
        for version_output, version in (
            ("qdl version v0.1", "0.1"),
            ("qdl version v1.0", "1.0"),
            ("qdl version v1.9", "1.9"),
            # compared as numbers, not as strings
            ("qdl version v1.10", "1.10"),
            ("qdl version 1.0-1~bpo13+1", "1.0"),
            ("qdl version 1:1.9-1", "1.9"),
        ):
            with self.subTest(version_output=version_output):
                self.assert_version_too_low(version_output, version)

    def test_qdl_version_unparsable(self):
        for version_output in (
            "",
            "qdl: unrecognized option '--version'",
            "qdl version unknown",
            "qdl version\n",
            "some other tool version v2.7",
        ):
            with self.subTest(version_output=version_output):
                self.assert_version_unparsable(version_output)
