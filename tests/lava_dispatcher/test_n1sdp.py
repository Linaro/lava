# Copyright (C) 2021 Arm Limited
#
# Author: Malcolm Brooks <malcolm.brooks@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class N1sdpFactory(Factory):
    def create_n1sdp_job(self, filename):  # pylint: disable=no-self-use
        return self.create_job("n1sdp-01.jinja2", filename)


class TestN1sdp(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = N1sdpFactory()
        self.job = self.factory.create_n1sdp_job(
            "sample_jobs/n1sdp-fw-grub-ramdisk.yaml"
        )

    def test_pipeline(self):
        self.job.validate()
        description_ref = self.pipeline_reference(
            "n1sdp-fw-grub-ramdisk.yaml", job=self.job
        )
        self.assertEqual(description_ref, self.job.pipeline.describe())
