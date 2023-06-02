# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from lava_scheduler_app.models import TestJob
from lava_scheduler_app.utils import mkdir


class Command(BaseCommand):
    help = "Move job outputs into the new location"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            default=False,
            action="store_true",
            help="Do not move any data, simulate the output",
        )
        parser.add_argument(
            "--slow",
            default=False,
            action="store_true",
            help="Be nice with the system by sleeping regularly",
        )

    def handle(self, *_, **options):
        base_dir = "/var/lib/lava-server/default/media/job-output/"
        len_base_dir = len(base_dir)
        jobs = TestJob.objects.all().order_by("id")

        self.stdout.write("Browsing all jobs")
        start = 0
        while True:
            count = 0
            for job in jobs[start : start + 100]:
                count += 1
                old_path = os.path.join(
                    settings.MEDIA_ROOT, "job-output", "job-%s" % job.id
                )
                date_path = os.path.join(
                    settings.MEDIA_ROOT,
                    "job-output",
                    "%02d" % job.submit_time.year,
                    "%02d" % job.submit_time.month,
                    "%02d" % job.submit_time.day,
                    str(job.id),
                )
                if not os.path.exists(old_path):
                    self.stdout.write("* %d skip" % job.id)
                    continue

                self.stdout.write(
                    "* %d {%s => %s}"
                    % (job.id, old_path[len_base_dir:], date_path[len_base_dir:])
                )
                if not options["dry_run"]:
                    mkdir(os.path.dirname(date_path))
                    if not os.path.exists(old_path):
                        self.stdout.write("  -> no output directory")
                        continue
                    os.rename(old_path, date_path)
            start += count
            if count == 0:
                break
            if options["slow"]:
                self.stdout.write("sleeping 2s...")
                time.sleep(2)
