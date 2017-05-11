# Copyright (C) 2016 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import glob
import os

from django.db.utils import IntegrityError
from django.core.management.base import BaseCommand

from lava_scheduler_app.models import DeviceType


class Command(BaseCommand):
    help = "Adding device types to this LAVA instance"

    def add_arguments(self, parser):
        parser.add_argument("device-types", nargs="*",
                            help="A list of device types. Passing '*' will add all known device types.")
        parser.add_argument("--list",
                            default=False,
                            action="store_true",
                            help="Listing all the available device types")

        health = parser.add_argument_group("health check", "Only supported when creating a single device-type")
        health.add_argument("--health-check",
                            default=None,
                            help="The health check (filename) for the given device type.")
        health.add_argument("--health-frequency",
                            default=24,
                            help="How often to run health checks.")
        health.add_argument("--health-denominator",
                            default="hours",
                            choices=["hours", "jobs"],
                            help="Initiate health checks by hours or by jobs.")

    def available_device_types(self):
        # List the available device types
        available_types = []
        for fname in glob.iglob("/etc/lava-server/dispatcher-config/device-types/*.jinja2"):
            device_type = os.path.basename(fname[:-7])
            if not device_type.startswith("base"):
                available_types.append(device_type)
        available_types.sort()
        return available_types

    def handle(self, *args, **options):
        self.stderr.write("This command is deprecated, use \"device-types\" instead")

        available_types = self.available_device_types()
        # List the available device types if requested
        if options["list"]:
            self.stdout.write("Available device types:")
            for device_type in available_types:
                self.stdout.write("- %s" % device_type)
            return

        # Check that we have at least one device type
        if len(options["device-types"]) == 0:
            self.stderr.write("Device type name not specified")
            return

        # Expand the "*" if needed
        device_types = options["device-types"]
        if device_types == ["*"]:
            device_types = available_types
        # Sort and remove duplications
        device_types = list(set(device_types))
        device_types.sort()

        # Check that heal-check can only be used with one device type
        if options["health_check"] is not None and len(device_types) != 1:
            self.stderr.write("'--health-check' can only be used with one device type at a time")
            return

        # Compute the max length
        max_length = 0
        for device in device_types:
            max_length = max(max_length, len(device))

        # Create the format string
        fmt_str = "- %%-%ds" % (max_length + 1)
        self.stdout.write("Adding the device types:")
        for device_type in device_types:
            self.stdout.write(fmt_str % device_type, ending="")
            if device_type not in available_types:
                self.stdout.write(" => Unknown type (not listed in /etc/lava-server/dispatcher-config/device-types/), skipped")
                continue
            try:
                if options["health_check"] is not None:
                    health_job = open(options["health_check"]).read()
                else:
                    health_job = None

                if options["health_denominator"] == "hours":
                    health_denominator = DeviceType.HEALTH_PER_HOUR
                else:
                    health_denominator = DeviceType.HEALTH_PER_JOB

                dt = DeviceType.objects.create(name=device_type,
                                               health_check_job=health_job,
                                               health_frequency=options["health_frequency"],
                                               health_denominator=health_denominator)
                dt.save()
                self.stdout.write("[OK]")
            except IntegrityError:
                self.stdout.write("[skip] (already installed)")
