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

from lava_scheduler_app.models import Device, LogEntry


def parse_health_transition(change_message):
    parts = change_message.split("→")
    if len(parts) != 2:
        return None

    old_health = parts[0].strip()
    new_health = parts[1].strip().split(" ")[0]
    return {"old_health": old_health, "new_health": new_health}


class Command(BaseCommand):
    help = "Export LAVA device health transitions to a JSON file."

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

    def handle(self, *args, **options):
        output_dir = options["output_dir"]

        today = datetime.today().date()
        if options["start_date"]:
            start_date = parse_date(options["start_date"])
        else:
            start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

        if not start_date:
            self.stderr.write(
                self.style.ERROR("Invalid date format. Please use YYYY-MM-DD.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Exporting transitions since {start_date}")
        )

        os.makedirs(output_dir, exist_ok=True)

        start_datetime = make_aware(datetime.combine(start_date, datetime.min.time()))
        self._export_transitions(output_dir, start_datetime)

    def _export_transitions(self, output_dir, start_datetime):
        self.stdout.write("Exporting device health transitions...")
        transitions_data = []
        try:
            for device in Device.objects.all():
                log_entries = (
                    LogEntry.objects.filter(
                        object_id=device.hostname,
                        action_time__gte=start_datetime,
                        change_message__contains="→",
                    )
                    .order_by("-action_time")
                    .select_related("user")
                    .iterator()
                )

                for t in log_entries:
                    data = {
                        "id": t.id,
                        "action_time": t.action_time.isoformat(),
                        "change_message": t.change_message,
                        "device_name": device.hostname,
                    }
                    health_transition = parse_health_transition(t.change_message)
                    if health_transition:
                        data.update(health_transition)
                    transitions_data.append(data)

            filename = f"transitions_{start_datetime.date()}.json"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "w") as f:
                json.dump(transitions_data, f, indent=2)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully exported {len(transitions_data)} health transitions to {filepath}"
                )
            )

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(
                    f"An error occurred during health transition export: {e}"
                )
            )
