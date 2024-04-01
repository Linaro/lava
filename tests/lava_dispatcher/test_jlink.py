# Copyright (C) 2019 Linaro Limited
# Copyright 2024 NXP
#
# Author: Andrei Gansari <andrei.gansari@linaro.org>
#         Andy Sabathier <andy.sabathier@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from unittest.mock import MagicMock, Mock, patch

from lava_common.exceptions import JobError
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class JLinkFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_kw36zj_board_id_unset(self, filename):
        return self.create_job("frdm-kw36zj-02", filename)

    def create_kw36zj_job_flash_only(self, filename):
        return self.create_job("frdm-kw36zj-01", filename)

    def create_rw610bga_job_multiple_flash(self, filename):
        return self.create_job("rw610bga-fr01", filename)

    def create_mimxrt1180_coretype_not_supported(self, filename):
        return self.create_job("mimxrt1180-evk-01", filename)


@patch("time.sleep", Mock())
class TestJLinkAction(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = JLinkFactory()

    @patch("subprocess.run")
    def test_pipeline_jlink_single_flash(self, mock_run):
        job = self.factory.create_kw36zj_job_flash_only(
            "sample_jobs/jlink-flash-single.yaml"
        )
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="SEGGER J-Link Commander V7.94b (Compiled Dec 13 2023 17:05:47)",
        )
        job.validate()
        self.assertEqual(
            self.pipeline_reference("jlink-flash-single.yaml", job=job),
            job.pipeline.describe(),
        )

    @patch("subprocess.run")
    def test_pipeline_jlink_multiple_flash(self, mock_run):
        # Test multiple flash
        job = self.factory.create_rw610bga_job_multiple_flash(
            "sample_jobs/jlink-flash-multiple.yaml"
        )
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="SEGGER J-Link Commander V7.94b (Compiled Dec 13 2023 17:05:47)",
        )
        job.validate()
        self.assertEqual(
            self.pipeline_reference("jlink-flash-multiple.yaml", job=job),
            job.pipeline.describe(),
        )

    @patch("subprocess.run")
    def test_jlink_not_installed(self, mock_run):
        job = self.factory.create_kw36zj_job_flash_only(
            "sample_jobs/jlink-flash-single.yaml"
        )
        # Check if the correct error appears when jlink is not installed
        mock_run.side_effect = FileNotFoundError
        with self.assertRaises(JobError):
            job.validate()

    @patch("subprocess.run")
    def test_jlink_command_failure(self, mock_run):
        job = self.factory.create_kw36zj_job_flash_only(
            "sample_jobs/jlink-flash-single.yaml"
        )
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        with self.assertRaises(JobError):
            job.validate()

    @patch("subprocess.run")
    def test_board_id_unset(self, mock_run):
        job = self.factory.create_kw36zj_board_id_unset(
            "sample_jobs/jlink-flash-single.yaml"
        )
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="SEGGER J-Link Commander V7.94b (Compiled Dec 13 2023 17:05:47)",
        )
        with self.assertRaises(JobError) as context:
            job.validate()
        self.assertEqual(
            str(context.exception), "Invalid job data: ['[JLink] board_id unset']\n"
        )

    @patch("subprocess.run")
    def test_coretype_not_supported(self, mock_run):
        job = self.factory.create_mimxrt1180_coretype_not_supported(
            "sample_jobs/jlink-flash-wrong-coretype.yaml"
        )
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="SEGGER J-Link Commander V7.94b (Compiled Dec 13 2023 17:05:47)",
        )
        with self.assertRaises(JobError) as context:
            job.validate()
        self.assertEqual(
            str(context.exception),
            "Invalid job data: [\"[coretype = M36] Not supported by current device (supported_core_types = ['M33', 'M7']).\"]\n",
        )
