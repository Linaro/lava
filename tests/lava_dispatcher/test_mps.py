# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Birch <dean.birch@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class MpsFactory(Factory):
    def create_mps_job(self, filename):
        return self.create_job("mps2plus-01.jinja2", filename)


class TestMps(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = MpsFactory()

    def test_mps_reference(self):
        job = self.factory.create_mps_job("sample_jobs/mps2plus.yaml")
        job.validate()
        self.assertEqual([], job.pipeline.errors)
        description_ref = self.pipeline_reference("mps2plus.yaml", job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_mps_reference_multiple(self):
        job = self.factory.create_mps_job("sample_jobs/mps2plus-multiple.yaml")
        job.validate()
        self.assertEqual([], job.pipeline.errors)
        description_ref = self.pipeline_reference("mps2plus-multiple.yaml", job)
        self.assertEqual(description_ref, job.pipeline.describe())
