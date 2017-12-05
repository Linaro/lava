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

from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser
)
from django.db import transaction

from lava_scheduler_app.models import (
    Device,
    DeviceType,
    Tag,
    Worker
)


class Command(BaseCommand):
    help = "Manage devices"

    device_state = {
        "IDLE": Device.STATE_IDLE,
        "RESERVED": Device.STATE_RESERVED,
        "RUNNING": Device.STATE_RUNNING
    }
    device_health = {
        "GOOD": Device.HEALTH_GOOD,
        "UNKNOWN": Device.HEALTH_UNKNOWN,
        "LOOPING": Device.HEALTH_LOOPING,
        "BAD": Device.HEALTH_BAD,
        "MAINTENANCE": Device.HEALTH_MAINTENANCE,
        "RETIRED": Device.HEALTH_RETIRED
    }

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
        sub.required = True

        # "add" sub-command
        add_parser = sub.add_parser("add", help="Add a device")
        add_parser.add_argument("hostname",
                                help="Hostname of the device")
        add_parser.add_argument("--device-type", required=True,
                                help="Device type")
        add_parser.add_argument("--description", default=None,
                                help="Device description")
        add_parser.add_argument("--offline", action="store_false",
                                dest="online", default=True,
                                help="Create the device offline (online by default)")
        add_parser.add_argument("--private", action="store_false",
                                dest="public", default=True,
                                help="Make the device private (public by default)")
        add_parser.add_argument("--worker", required=True,
                                help="The name of the worker")
        add_parser.add_argument("--tags", nargs="*", required=False,
                                help="List of tags to add to the device")

        # "details" sub-command
        details_parser = sub.add_parser("details", help="Details about a device")
        details_parser.add_argument("hostname",
                                    help="Hostname of the device")

        # "list" sub-command
        list_parser = sub.add_parser("list", help="List the installed devices")
        list_parser.add_argument("--state", default=None,
                                 choices=["IDLE", "RESERVED", "RUNNING"],
                                 help="Show only devices with the given state")
        health = list_parser.add_mutually_exclusive_group()
        health.add_argument("--all", "-a", dest="show_all",
                            default=None, action="store_true",
                            help="Show all devices, including retired ones")
        health.add_argument("--health", default=None,
                            choices=["GOOD", "UNKNOWN", "LOOPING", "BAD", "MAINTENANCE", "RETIRED"],
                            help="Show only devices with the given health")
        list_parser.add_argument("--csv", dest="csv", default=False,
                                 action="store_true", help="Print as csv")

        # "set" sub-command
        set_parser = sub.add_parser("set", help="Set properties of the given device")
        set_parser.add_argument("hostname",
                                help="Hostname of the device")
        set_parser.add_argument("--description", default=None,
                                help="Set the description")
        display = set_parser.add_mutually_exclusive_group()
        display.add_argument("--public", default=None, action="store_true",
                             help="make the device public")
        display.add_argument("--private", dest="public", action="store_false",
                             help="Make the device private")
        update_parser.add_argument("--health", default=None,
                                   choices=["GOOD", "UNKNOWN", "LOOPING", "BAD", "MAINTENANCE", "RETIRED"],
                                   help="Update the device health")
        update_parser.add_argument("--worker", default=None,
                                   help="Update the worker")

    def handle(self, *args, **options):
        """ Forward to the right sub-handler """
        if options["sub_command"] == "add":
            self.handle_add(options["hostname"], options["device_type"],
                            options["worker"], options["description"],
                            options["public"], options["online"],
                            options["tags"])
        elif options["sub_command"] == "details":
            self.handle_details(options["hostname"])
        elif options["sub_command"] == "list":
            self.handle_list(options["state"], options["health"],
                             options["show_all"], options["csv"])
        else:
            self.handle_set(options)

    def handle_add(self, hostname, device_type, worker_name,
                   description, public, online, tags):
        try:
            dt = DeviceType.objects.get(name=device_type)
        except DeviceType.DoesNotExist:
            raise CommandError("Unable to find device-type '%s'" % device_type)

        try:
            worker = Worker.objects.get(hostname=worker_name)
        except Worker.DoesNotExist:
            raise CommandError("Unable to find worker '%s'" % worker_name)

        health = Device.HEALTH_GOOD if online else Device.HEALTH_MAINTENANCE
        device = Device.objects.create(hostname=hostname, device_type=dt,
                                       description=description,
                                       worker_host=worker, is_pipeline=True,
                                       state=Device.STATE_IDLE, health=health,
                                       is_public=public)

        if tags is not None:
            for tag in tags:
                device.tags.add(Tag.objects.get_or_create(name=tag)[0])

    def handle_details(self, hostname):
        """ Print device details """
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise CommandError("Unable to find device '%s'" % hostname)

        self.stdout.write("hostname   : %s" % hostname)
        self.stdout.write("device-type: %s" % device.device_type.name)
        self.stdout.write("state      : %s" % device.get_state_display())
        self.stdout.write("health     : %s" % device.get_health_display())
        self.stdout.write("health job : %s" % bool(device.get_health_check()))
        self.stdout.write("description: %s" % device.description)
        self.stdout.write("public     : %s" % device.is_public)

        config = device.load_configuration(output_format="raw")
        self.stdout.write("device-dict: %s" % bool(config))
        self.stdout.write("worker     : %s" % device.worker_host.hostname)
        self.stdout.write("current_job: %s" % device.current_job())

    def handle_list(self, state, health, show_all, format_as_csv):
        """ Print devices list """
        devices = Device.objects.all().order_by("hostname")
        if state is not None:
            devices = devices.filter(state=self.device_state[state])

        if health is not None:
            devices = devices.filter(health=self.device_health[health])
        elif not show_all:
            devices = devices.exclude(health=Device.HEALTH_RETIRED)

        if format_as_csv:
            fields = ["hostname", "device-type", "state", "health"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for device in devices:
                writer.writerow({
                    "hostname": device.hostname,
                    "device-type": device.device_type.name,
                    "state": device.get_state_display(),
                    "health": device.get_health_display()
                })
        else:
            self.stdout.write("Available devices:")
            for device in devices:
                self.stdout.write("* %s (%s) %s, %s" % (device.hostname,
                                                        device.device_type.name,
                                                        device.get_state_display(),
                                                        device.get_health_display()))

    def handle_update(self, options):
        """ Update device properties """
        with transaction.atomic():
            hostname = options["hostname"]
            try:
                device = Device.objects.select_for_update().get(hostname=hostname)
            except Device.DoesNotExist:
                raise CommandError("Unable to find device '%s'" % hostname)

            health = options["health"]
            if health is not None:
                device.health = self.device_health[health]

            description = options["description"]
            if description is not None:
                device.description = description

            worker_name = options["worker"]
            if worker_name is not None:
                try:
                    worker = Worker.objects.get(hostname=worker_name)
                    device.worker_host = worker
                except Worker.DoesNotExist:
                    raise CommandError("Unable to find worker '%s'" % worker_name)

            public = options["public"]
            if public is not None:
                device.is_public = public

            # Save the modifications
            device.save()
