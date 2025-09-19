# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import Mock, patch

from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class UBootDFUFactory(Factory):
    def create_rzn1d_job(self, filename):
        return self.create_job("rzn1d-01", filename)


class TestUbootDFUAction(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = UBootDFUFactory()

    def test_enter_dfu_action(self):
        job = self.factory.create_rzn1d_job("sample_jobs/rzn1d-dfu.yaml")
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference("rzn1d-dfu.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        with patch(
            "lava_dispatcher.actions.boot.dfu.which",
            Mock(return_value="/usr/bin/dfu-util"),
        ) as which_mock:
            self.assertIsNone(job.validate())

        which_mock.assert_called_once_with("dfu-util")
