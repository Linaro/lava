# Copyright (C) 2020 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from importlib import import_module

from django.core.management.base import BaseCommand

from lava_common.exceptions import ConfigurationError
from lava_scheduler_app.logutils import LogsFilesystem
from lava_scheduler_app.models import TestJob


class Command(BaseCommand):
    help = "Copy logs from filesystem to alternative logging db storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simulate the execution (do not store logs in db)",
        )
        parser.add_argument(
            "db",
            type=str,
            default="LogsMongo",
            choices=["LogsMongo", "LogsElasticsearch"],
            nargs="?",
            help="Database storage choice. Options: LogsMongo, LogsElasticsearch.",
        )

    def handle(self, *_, **options):
        backend_str = "lava_scheduler_app.logutils"
        if options["db"] == "LogsFilesystem":
            self.stdout.write("Cannot move logs from filesystem to filesystem.")

        try:
            logs_class = getattr(import_module(backend_str), options["db"])
        except (AttributeError, ModuleNotFoundError) as exc:
            self.stdout.write("Please provide a valid database backend.")

        try:
            logs_db = logs_class()
        except ConfigurationError as e:
            self.stdout.write(str(e))
            return

        self.stdout.write("Copying logs:")
        # Read from filesystem.
        logs_filesystem = LogsFilesystem()

        for job in TestJob.objects.all().order_by("id"):
            if logs_db.line_count(job) > 0:
                # We already have logs for the given job.
                self.stdout.write(
                    f"* {job.id} [SKIP] - Logs already present for this job."
                )
                continue
            try:
                lines = logs_filesystem.read(job)
            except FileNotFoundError:
                self.stdout.write(f"* {job.id} [SKIP] - Log file not found")
                continue
            except Exception as e:
                self.stdout.write(f"* {job.id} [SKIP] - {str(e)}")
                continue

            self.stdout.write(f"* {job.id}")
            if not options["dry_run"]:
                for index, line in enumerate(lines.strip("\n").split("\n")):
                    if line:
                        try:
                            logs_db.write(job, line)
                        except Exception:
                            self.stdout.write(f"  -> Invalid line {index}")
        self.stdout.write("Done.")
