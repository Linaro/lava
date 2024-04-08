# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path

from tests.lava_dispatcher.test_basic import LavaDispatcherTestCase


class TestJob(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.job = self.create_simple_job()

    def test_tmp_dir(self):
        self.assertIsNotNone(self.job.tmp_dir)
        tmp_dir = Path(self.job.tmp_dir)
        self.assertFalse(tmp_dir.exists())
        self.assertEqual(tmp_dir.name, str(self.job.job_id))

    def test_tmp_dir_with_prefix(self):
        self.job.parameters["dispatcher"] = {"prefix": "FOOBAR-"}
        tmp_dir = Path(self.job.tmp_dir)
        self.assertEqual(tmp_dir.name, f"FOOBAR-{self.job.job_id}")

    def test_mkdtemp(self):
        d = self.job.mkdtemp("my-action")
        self.assertTrue(Path(d).exists())
        self.assertIn("my-action", d)

    def test_mkdtemp_with_prefix(self):
        self.job.parameters["dispatcher"] = {"prefix": "FOOBAR-"}
        d = Path(self.job.mkdtemp("my-action"))
        self.assertEqual(d.parent.name, f"FOOBAR-{self.job.job_id}")

    def test_mktemp_with_override(self):
        tmp_dir_path = self.create_temporary_directory()
        override = tmp_dir_path / "override"
        first = Path(self.job.mkdtemp("my-action", override=override))
        second = Path(self.job.mkdtemp("my-assert", override=override))
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, second.parent)
        self.assertEqual(first.parent.name, str(self.job.job_id))
