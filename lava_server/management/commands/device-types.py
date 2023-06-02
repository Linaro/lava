# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from lava_scheduler_app.models import Alias, DeviceType
from lava_server.files import File


class Command(BaseCommand):
    help = (
        "Manage device types according to which templates are available "
        "and which device-types are defined in the database. When counting "
        "the number of devices, Retired devices are included."
    )

    def add_arguments(self, parser):
        sub = parser.add_subparsers(
            dest="sub_command",
            help="Sub commands",
        )
        sub.required = True

        # "add" sub-command
        add_parser = sub.add_parser(
            "add", help="Add V2 device type(s) to the database."
        )
        add_parser.add_argument(
            "device-type",
            help="The device type name. "
            "Passing '*' will add all known V2 device types.",
        )
        alias = add_parser.add_argument_group(
            "alias", "Only supported when creating a single device-type"
        )
        alias.add_argument(
            "--alias", default="", help="Name of an alias for this device-type."
        )
        health = add_parser.add_argument_group(
            "health check", "Only supported when creating a single device-type"
        )
        health.add_argument(
            "--health-frequency", default=24, help="How often to run health checks."
        )
        health.add_argument(
            "--health-denominator",
            default="hours",
            choices=["hours", "jobs"],
            help="Initiate health checks by hours or by jobs.",
        )

        # "update" sub-command
        update_parser = sub.add_parser(
            "update", help="Update an existing V2 device type in the database."
        )
        update_parser.add_argument("device-type", help="The device type name.")
        update_alias = update_parser.add_argument_group("alias")
        update_alias.add_argument(
            "--alias", required=True, help="Name of an alias for this device-type."
        )

        # "details" sub-command
        details_parser = sub.add_parser("details", help="Details about a device-type")
        details_parser.add_argument("name", help="Name of the device-type")
        details_parser.add_argument(
            "--devices",
            action="store_true",
            default=False,
            help="Print the corresponding devices",
        )

        # "list" sub-command
        list_parser = sub.add_parser("list", help="List the installed device types")
        list_parser.add_argument(
            "--all",
            "-a",
            dest="show_all",
            default=False,
            action="store_true",
            help="Show all device types in the database, "
            "including non-installed ones",
        )
        list_parser.add_argument(
            "--csv", dest="csv", default=False, action="store_true", help="Print as csv"
        )

    def available_device_types(self):
        """List available device types by looking at the configuration files"""
        available_types = []
        for device_type in File("device-type").list("*.jinja2"):
            if not device_type.startswith("base"):
                available_types.append(device_type[:-7])
        available_types.sort()
        return available_types

    def handle(self, *args, **options):
        """Forward to the right sub-handler"""
        if options["sub_command"] == "add":
            self.handle_add(
                options["device-type"],
                options["alias"],
                options["health_denominator"],
                options["health_frequency"],
            )
        elif options["sub_command"] == "details":
            self.handle_details(options["name"], options["devices"])
        elif options["sub_command"] == "update":
            self.handle_update(options["device-type"], options["alias"])
        else:
            self.handle_list(options["show_all"], options["csv"])

    def handle_update(self, device_type, alias):
        """Update an existing device type"""
        if not alias:
            raise CommandError("No alias was specified to update '%s'" % device_type)
        try:
            dt = device_type = DeviceType.objects.get(name=device_type)
            _, created = Alias.objects.get_or_create(name=alias, device_type=dt)
            if not created:
                self.stdout.write("Alias '%s' already exists" % alias)
        except DeviceType.DoesNotExist:
            raise CommandError("Unable to find device-type '%s'" % device_type)
        except IntegrityError:
            raise CommandError("Alias '%s' already used by other device type")

    def handle_add(self, device_type, alias, health_denominator, health_frequency):
        """Add a device type"""
        with contextlib.suppress(DeviceType.DoesNotExist):
            DeviceType.objects.get(name=device_type)
            raise CommandError("Device-type '%s' already exists" % device_type)

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
            if health_denominator == "hours":
                health_denominator = DeviceType.HEALTH_PER_HOUR
            else:
                health_denominator = DeviceType.HEALTH_PER_JOB

            dt = DeviceType.objects.create(
                name=device_type,
                health_frequency=health_frequency,
                health_denominator=health_denominator,
            )
            if alias:
                try:
                    Alias.objects.create(name=alias, device_type=dt)
                except IntegrityError:
                    raise CommandError("Alias '%s' already used by other device type")

    def handle_details(self, name, devices):
        """Print some details about the device-type"""
        try:
            device_type = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            raise CommandError("Unable to find device-type '%s'" % name)

        aliases = [str(alias.name) for alias in device_type.aliases.all()]
        self.stdout.write("device_type    : %s" % name)
        self.stdout.write("description    : %s" % device_type.description)
        self.stdout.write("display        : %s" % device_type.display)
        self.stdout.write("health disabled: %s" % device_type.disable_health_check)
        self.stdout.write("aliases        : %s" % aliases)
        if not devices:
            self.stdout.write("devices        : %d" % device_type.device_set.count())
        else:
            self.stdout.write("devices        :")
            for device in device_type.device_set.all():
                self.stdout.write("- %s" % device.hostname)

    def handle_list(self, show_all, format_as_csv):
        """List the device types"""
        available_types = self.available_device_types()
        device_type_names = []
        device_types = DeviceType.objects.all().order_by("name")
        if show_all:
            device_type_names = [dt.name for dt in device_types]
            available_types = self.available_device_types()

        if format_as_csv:
            fields = ["name", "devices", "installed", "template"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for dt in device_types:
                writer.writerow(
                    {
                        "name": dt.name,
                        "devices": dt.device_set.count(),
                        "installed": True,
                        "template": dt.name in available_types,
                    }
                )

            if show_all:
                for dt in available_types:
                    if dt not in device_type_names:
                        writer.writerow(
                            {
                                "name": dt,
                                "devices": 0,
                                "installed": False,
                                "template": True,
                            }
                        )
        else:
            self.stdout.write("Installed device types:")
            for dt in device_types:
                v2msg = "" if dt.name in available_types else "- No V2 template."
                self.stdout.write(
                    "* %s (%d devices) %s" % (dt.name, dt.device_set.count(), v2msg)
                )

            if show_all:
                self.stdout.write("Available V2 device types:")
                for dt in available_types:
                    if dt not in device_type_names:
                        self.stdout.write("* %s" % dt)
