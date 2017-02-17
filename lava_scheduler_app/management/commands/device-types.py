# Copyright (C) 2017 Linaro Limited
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

import csv
import glob
import os
import sys

from django.core.management.base import BaseCommand, CommandParser

from lava_scheduler_app.models import DeviceType
# pylint: disable=invalid-name,no-self-use


class Command(BaseCommand):
    help = "Manage device types according to which templates are available " \
           "and which device-types are defined in the database. When counting " \
           "the number of devices, Retired devices are included."

    def add_arguments(self, parser):
        cmd = self

        class SubParser(CommandParser):
            """
            Sub-parsers constructor that mimic Django constructor.
            See http://stackoverflow.com/a/37414551
            """
            def __init__(self, **kwargs):
                super(SubParser, self).__init__(cmd, **kwargs)

        sub = parser.add_subparsers(dest="sub_command", help="Sub commands", parser_class=SubParser)

        # "add" sub-command
        add_parser = sub.add_parser("add", help="Add V2 device type(s) to the database.")
        add_parser.add_argument("device-type",
                                help="The device type name. "
                                     "Passing '*' will add all known V2 device types.")
        health = add_parser.add_argument_group("health check",
                                               "Only supported when creating a single device-type")
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

        # "details" sub-command
        details_parser = sub.add_parser("details", help="Details about a device-type")
        details_parser.add_argument("name",
                                    help="Name of the device-type")
        details_parser.add_argument("--devices", action="store_true",
                                    default=False,
                                    help="Print the corresponding devices")

        # "list" sub-command
        list_parser = sub.add_parser("list", help="List the installed device types")
        list_parser.add_argument("--all", "-a", dest="show_all",
                                 default=False, action="store_true",
                                 help="Show all device types in the database, "
                                      "including non-installed ones")
        list_parser.add_argument("--csv", dest="csv", default=False,
                                 action="store_true", help="Print as csv")

    def available_device_types(self):
        """ List avaiable device types by looking at the configuration files """
        available_types = []
        for fname in glob.iglob("/etc/lava-server/dispatcher-config/device-types/*.jinja2"):
            device_type = os.path.basename(fname[:-7])
            if not device_type.startswith("base"):
                available_types.append(device_type)
        available_types.sort()
        return available_types

    def handle(self, *args, **options):
        """ Forward to the right sub-handler """
        if options["sub_command"] == "add":
            self.handle_add(options["device-type"], options["health_check"],
                            options["health_denominator"],
                            options["health_frequency"])
        elif options["sub_command"] == "details":
            self.handle_details(options["name"], options["devices"])
        else:
            self.handle_list(options["show_all"], options["csv"])

    def handle_add(self, device_type, health_check, health_denominator,
                   health_frequency):
        """ Add a device type """
        if device_type == "*":
            self.stdout.write("Adding all known device types")
            available_types = self.available_device_types()
            installed = [dt.name for dt in DeviceType.objects.all()]
            for dt_name in available_types:
                if dt_name in installed:
                    self.stdout.write("* %s [skip]" % dt_name)
                    continue
                self.stdout.write("* %s" % dt_name)
                DeviceType.objects.create(name=dt_name)
        else:
            if health_check is not None:
                health_job = open(health_check).read()
            else:
                health_job = None

            if health_denominator == "hours":
                health_denominator = DeviceType.HEALTH_PER_HOUR
            else:
                health_denominator = DeviceType.HEALTH_PER_JOB

            DeviceType.objects.create(
                name=device_type,
                health_check_job=health_job,
                health_frequency=health_frequency,
                health_denominator=health_denominator)

    def handle_details(self, name, devices):
        """ Print some details about the device-type """
        try:
            device_type = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            self.stderr.write("Unable to find device-type '%s'" % name)
            sys.exit(1)

        self.stdout.write("device_type : %s" % name)
        self.stdout.write("description : %s" % device_type.description)
        self.stdout.write("display     : %s" % device_type.display)
        self.stdout.write("owners_only : %s" % device_type.owners_only)
        self.stdout.write("health_check: %s" % bool(device_type.health_check_job))
        if not devices:
            self.stdout.write("devices     : %d" % device_type.device_set.count())
        else:
            self.stdout.write("devices     :")
            for device in device_type.device_set.all():
                self.stdout.write("- %s" % device.hostname)

    def handle_list(self, show_all, format_as_csv):
        """ List the device types """
        available_types = self.available_device_types()
        device_type_names = []
        device_types = DeviceType.objects.all().order_by('name')
        if show_all:
            device_type_names = [dt.name for dt in device_types]
            available_types = self.available_device_types()

        if format_as_csv:
            fields = ["name", "devices", "installed", "template"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for dt in device_types:
                writer.writerow({
                    "name": dt.name,
                    "devices": dt.device_set.count(),
                    "installed": True,
                    "template": dt.name in available_types
                })

            if show_all:
                for dt in available_types:
                    if dt not in device_type_names:
                        writer.writerow({
                            "name": dt,
                            "devices": 0,
                            "installed": False,
                            "template": True,
                        })
        else:
            self.stdout.write("Installed device types:")
            for dt in device_types:
                v2msg = '' if dt.name in available_types else "- No V2 template."
                self.stdout.write("* %s (%d devices) %s" % (dt.name, dt.device_set.count(), v2msg))

            if show_all:
                self.stdout.write("Available V2 device types:")
                for dt in available_types:
                    if dt not in device_type_names:
                        self.stdout.write("* %s" % dt)
