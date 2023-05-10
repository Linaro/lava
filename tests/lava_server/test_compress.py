# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from os import urandom
from pathlib import Path
from shutil import rmtree
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from lava_scheduler_app.logutils import LogsFilesystem
from lava_scheduler_app.models import TestJob


class TestJobCompression(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(
            "test_admin",
            "test@example.com",
            "12345",
        )
        self.job = TestJob.objects.create(
            submitter=self.user,
            state=TestJob.STATE_FINISHED,
        )
        self.log_system = LogsFilesystem()
        self.output_dir = Path(self.job.output_dir)
        try:
            rmtree(self.output_dir)
        except FileNotFoundError:
            ...
        self.output_dir.mkdir(parents=True)
        with open(
            self.output_dir / self.log_system.log_filename,
            mode="wb",
        ) as log_file:
            log_file.write(urandom(1024 * 30))

    def test_job_compression(self) -> None:
        with patch("lava_server.management.commands.jobs.chown"):
            call_command("jobs", "compress", f"--submitter={self.user.username}")

        self.assertFalse(
            (self.output_dir / self.log_system.log_filename).exists(),
            "Uncompressed log should be deleted",
        )

        self.assertTrue(
            (self.output_dir / self.log_system.compressed_log_filename).exists(),
            "Compressed log should exist",
        )
