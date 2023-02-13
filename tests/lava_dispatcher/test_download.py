# Copyright (C) 2017 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import unittest

from lava_common.exceptions import JobError
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import infrastructure_error_multi_paths


class TestDownloadDeploy(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job(
            "db410c-01.jinja2", "sample_jobs/download.yaml"
        )

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        self.assertIsInstance(self.job.device["device_info"], list)
        for action in self.job.pipeline.actions:
            self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = self.pipeline_reference("download.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    @unittest.skipIf(
        infrastructure_error_multi_paths(["lxc-info", "img2simg", "simg2img"]),
        "lxc or img2simg or simg2img not installed",
    )
    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_directories(self):
        job = self.factory.create_job("bbb-01.jinja2", "sample_jobs/download_dir.yaml")
        with self.assertRaises(JobError):
            job.validate()

    @unittest.skipIf(
        infrastructure_error_multi_paths(["nbd-server"]), "nbd-server not installed"
    )
    def test_download_tar(self):
        job = self.factory.create_job(
            "x86-01.jinja2", "sample_jobs/up2-tests-from-tar.yaml"
        )
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        description_ref = self.pipeline_reference("up2-tests-from-tar.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
