# Copyright (C) 2025 Linaro Limited
#
# Author: Ben Copeland <ben.copeland@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json
import os
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware

from lava_scheduler_app.models import TestJob


class Command(BaseCommand):
    help = "Export LAVA test jobs to a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            required=True,
            help="The directory where the JSON export files will be saved.",
        )
        parser.add_argument(
            "--start-date",
            help="The start date for the export in YYYY-MM-DD format. Defaults to the first day of the previous month.",
        )
        parser.add_argument(
            "--end-date",
            help="The end date for the export in YYYY-MM-DD format. Defaults to the last day of the previous month.",
        )

    def handle(self, *args, **options):
        output_dir = options["output_dir"]

        today = datetime.today().date()
        if options["start_date"]:
            start_date = parse_date(options["start_date"])
        else:
            start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

        if options["end_date"]:
            end_date = parse_date(options["end_date"])
        else:
            end_date = today.replace(day=1) - timedelta(days=1)

        if not start_date or not end_date:
            self.stderr.write(
                self.style.ERROR("Invalid date format. Please use YYYY-MM-DD.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Exporting test jobs from {start_date} to {end_date}")
        )

        os.makedirs(output_dir, exist_ok=True)

        self._export_test_jobs(output_dir, start_date, end_date)

    def _export_test_jobs(self, output_dir, start_date, end_date):
        self.stdout.write("Exporting test jobs...")
        testjobs_data = []
        try:
            start_datetime = make_aware(
                datetime.combine(start_date, datetime.min.time())
            )
            end_datetime = make_aware(datetime.combine(end_date, datetime.max.time()))

            jobs = (
                TestJob.objects.filter(
                    submit_time__gte=start_datetime, submit_time__lte=end_datetime
                )
                .prefetch_related(
                    "tags", "submitter", "requested_device_type", "actual_device"
                )
                .iterator()
            )

            for t in jobs:
                testjobs_data.append(
                    {
                        "id": t.id,
                        "submitter": t.submitter.username if t.submitter else None,
                        "description": t.description,
                        "health_check": t.health_check,
                        "requested_device_type": t.requested_device_type.name
                        if t.requested_device_type
                        else None,
                        "tags": [tag.name for tag in t.tags.all()],
                        "actual_device": t.actual_device.hostname
                        if t.actual_device
                        else None,
                        "submit_time": t.submit_time.isoformat()
                        if t.submit_time
                        else None,
                        "start_time": t.start_time.isoformat()
                        if t.start_time
                        else None,
                        "end_time": t.end_time.isoformat() if t.end_time else None,
                        "state": t.get_state_display(),
                        "health": t.get_health_display(),
                        "priority": t.priority,
                        "definition": t.definition,
                        "failure_comment": t.failure_comment,
                    }
                )

            filename = f"testjobs_{start_date}_{end_date}.json"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "w") as f:
                json.dump(testjobs_data, f, indent=2)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully exported {len(testjobs_data)} test jobs to {filepath}"
                )
            )

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"An error occurred during test job export: {e}")
            )
