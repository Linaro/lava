# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import unittest

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import infrastructure_error


class UBootDFUFactory(Factory):
    def create_rzn1d_job(self, filename):
        return self.create_job("rzn1d-01.jinja2", filename)


class TestUbootDFUAction(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = UBootDFUFactory()

    @unittest.skipIf(infrastructure_error("dfu-util"), "dfu-util not installed")
    def test_enter_dfu_action(self):
        job = self.factory.create_rzn1d_job("sample_jobs/rzn1d-dfu.yaml")
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference("rzn1d-dfu.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())
