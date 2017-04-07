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

import argparse
import csv
import sys

from django.core.management.base import BaseCommand, CommandParser

from lava_scheduler_app.models import (
    Device,
    DeviceDictionary,
    DeviceType,
    Worker
)
from lava_scheduler_app.utils import jinja2_to_devicedictionary


class Command(BaseCommand):
    help = "Manage devices"

    device_status = {
        "OFFLINE": Device.OFFLINE,
        "IDLE": Device.IDLE,
        "RUNNING": Device.RUNNING,
        "OFFLINING": Device.OFFLINING,
        "RETIRED": Device.RETIRED,
        "RESERVED": Device.RESERVED,
    }

    health_status = {
        "UNKNOWN": Device.HEALTH_UNKNOWN,
        "PASS": Device.HEALTH_PASS,
        "FAIL": Device.HEALTH_FAIL,
        "LOOPING": Device.HEALTH_LOOPING,
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

        # "add" sub-command
        add_parser = sub.add_parser("add", help="Add a device")
        add_parser.add_argument("hostname",
                                help="Hostname of the device")
        add_parser.add_argument("--device-type", required=True,
                                help="Device type")
        add_parser.add_argument("--description", default=None,
                                help="Device description")
        add_parser.add_argument("--dictionary", default=None,
                                type=argparse.FileType("r"),
                                help="Device dictionary")
        add_parser.add_argument("--non-pipeline", action="store_false",
                                dest="pipeline", default=True,
                                help="Create a v1 device (v2 by default)")
        add_parser.add_argument("--offline", action="store_false",
                                dest="online", default=True,
                                help="Create the device offline (online by default)")
        add_parser.add_argument("--private", action="store_false",
                                dest="public", default=True,
                                help="Make the device private (public by default)")
        add_parser.add_argument("--worker", required=True,
                                help="The name of the worker")

        # "details" sub-command
        details_parser = sub.add_parser("details", help="Details about a device")
        details_parser.add_argument("hostname",
                                    help="Hostname of the device")

        # "list" sub-command
        list_parser = sub.add_parser("list", help="List the installed devices")
        display = list_parser.add_mutually_exclusive_group()
        display.add_argument("--all", "-a", dest="show_all",
                             default=False, action="store_true",
                             help="Show all devices, including retired ones")
        display.add_argument("--status", default=None,
                             choices=["OFFLINE", "IDLE", "RUNNING",
                                      "OFFLINING", "RETIRED", "RESERVED"],
                             help="Show only devices with this status")
        list_parser.add_argument("--csv", dest="csv", default=False,
                                 action="store_true", help="Print as csv")

        # "set" sub-command
        set_parser = sub.add_parser("set", help="Set properties of the given device")
        set_parser.add_argument("hostname",
                                help="Hostname of the device")
        set_parser.add_argument("--description", default=None,
                                help="Set the description")
        set_parser.add_argument("--dictionary", default=None,
                                type=argparse.FileType("r"),
                                help="Device dictionary")
        display = set_parser.add_mutually_exclusive_group()
        display.add_argument("--public", default=None, action="store_true",
                             help="make the device public")
        display.add_argument("--private", dest="public", action="store_false",
                             help="Make the device private")
        set_parser.add_argument("--status", default=None,
                                choices=["OFFLINE", "IDLE", "RUNNING",
                                         "OFFLINING", "RETIRED", "RESERVED"],
                                help="Set the device status")
        set_parser.add_argument("--health", default=None,
                                choices=["UNKNOWN", "PASS", "FAIL", "LOOPING"],
                                help="Set the device health status")
        set_parser.add_argument("--worker", default=None,
                                help="Set the worker")

    def handle(self, *args, **options):
        """ Forward to the right sub-handler """
        if options["sub_command"] == "add":
            self.handle_add(options["hostname"], options["device_type"],
                            options["worker"], options["description"],
                            options["dictionary"], options["pipeline"],
                            options["public"], options["online"])
        elif options["sub_command"] == "details":
            self.handle_details(options["hostname"])
        elif options["sub_command"] == "list":
            self.handle_list(options["status"], options["show_all"],
                             options["csv"])
        else:
            self.handle_set(options)

    def handle_add(self, hostname, device_type, worker_name,
                   description, dictionary, pipeline, public, online):
        try:
            dt = DeviceType.objects.get(name=device_type)
        except DeviceType.DoesNotExist:
            self.stderr.write("Unable to find device-type '%s'" % device_type)
            sys.exit(1)
        try:
            worker = Worker.objects.get(hostname=worker_name)
        except Worker.DoesNotExist:
            self.stderr.write("Unable to find worker '%s'" % worker_name)
            sys.exit(1)

        status = Device.IDLE if online else Device.OFFLINE
        Device.objects.create(hostname=hostname, device_type=dt,
                              description=description, worker_host=worker,
                              is_pipeline=pipeline, status=status,
                              is_public=public)

        if dictionary is not None:
            data = jinja2_to_devicedictionary(dictionary.read())
            if data is None:
                self.stderr.write("Invalid device dictionary")
                sys.exit(1)
            element = DeviceDictionary(hostname=hostname)
            element.hostname = hostname
            element.parameters = data
            element.save()

    def handle_details(self, hostname):
        """ Print device details """
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            self.stderr.write("Unable to find device '%s'" % hostname)
            sys.exit(1)

        self.stdout.write("hostname   : %s" % hostname)
        self.stdout.write("device_type: %s" % device.device_type.name)
        self.stdout.write("status     : %s" % device.get_status_display())
        self.stdout.write("health     : %s" % device.get_health_status_display())
        self.stdout.write("health job : %s" % bool(device.get_health_check()))
        self.stdout.write("description: %s" % device.description)
        self.stdout.write("public     : %s" % device.is_public)
        self.stdout.write("pipeline   : %s" % device.is_pipeline)

        element = DeviceDictionary.get(hostname)
        self.stdout.write("device-dict: %s" % bool(element))
        self.stdout.write("worker     : %s" % device.worker_host.hostname)
        self.stdout.write("current_job: %s" % device.current_job)

    def handle_list(self, status, show_all, format_as_csv):
        """ Print devices list """
        devices = Device.objects.all().order_by("hostname")
        if status is not None:
            devices = devices.filter(status=self.device_status[status])
        elif not show_all:
            devices = devices.exclude(status=Device.RETIRED)

        if format_as_csv:
            fields = ["hostname", "device-type", "status"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for device in devices:
                writer.writerow({
                    "hostname": device.hostname,
                    "device-type": device.device_type.name,
                    "status": device.get_status_display()
                })
        else:
            self.stdout.write("Available devices:")
            for device in devices:
                self.stdout.write("* %s (%s) %s" % (device.hostname,
                                                    device.device_type.name,
                                                    device.get_status_display()))

    def handle_set(self, options):
        """ Set device properties """
        hostname = options["hostname"]
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            self.stderr.write("Unable to find device '%s'" % hostname)
            sys.exit(1)

        status = options["status"]
        if status is not None:
            device.status = self.device_status[status]

        health = options["health"]
        if health is not None:
            device.health_status = self.health_status[health]

        description = options["description"]
        if description is not None:
            device.description = description

        worker_name = options["worker"]
        if worker_name is not None:
            try:
                worker = Worker.objects.get(hostname=worker_name)
                device.worker_host = worker
            except Worker.DoesNotExist:
                self.stderr.write("Unable to find worker '%s'" % worker_name)
                sys.exit(1)

        public = options["public"]
        if public is not None:
            device.is_public = public

        dictionary = options["dictionary"]
        if dictionary is not None:
            data = jinja2_to_devicedictionary(dictionary.read())
            if data is None:
                self.stderr.write("Invalid device dictionary")
                sys.exit(1)
            element = DeviceDictionary.get(hostname)
            if element is None:
                element = DeviceDictionary(hostname=hostname)
                element.hostname = hostname
            element.parameters = data
            element.save()

        # Save the modifications
        device.save()
