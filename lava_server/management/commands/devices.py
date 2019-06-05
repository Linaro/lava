# -*- coding: utf-8 -*-
# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import os
import contextlib
import csv

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import User, Group
from lava_scheduler_app.models import Device, DeviceType, Tag, Worker

# pylint: disable=bad-continuation


class Command(BaseCommand):
    help = "Manage devices"

    device_state = {
        "IDLE": Device.STATE_IDLE,
        "RESERVED": Device.STATE_RESERVED,
        "RUNNING": Device.STATE_RUNNING,
    }
    device_health = {
        "GOOD": Device.HEALTH_GOOD,
        "UNKNOWN": Device.HEALTH_UNKNOWN,
        "LOOPING": Device.HEALTH_LOOPING,
        "BAD": Device.HEALTH_BAD,
        "MAINTENANCE": Device.HEALTH_MAINTENANCE,
        "RETIRED": Device.HEALTH_RETIRED,
    }

    def add_arguments(self, parser):
        cmd = self

        class SubParser(CommandParser):
            """
            Sub-parsers constructor that mimic Django constructor.
            See http://stackoverflow.com/a/37414551
            """

            def __init__(self, **kwargs):
                super().__init__(cmd, **kwargs)

        sub = parser.add_subparsers(
            dest="sub_command", help="Sub commands", parser_class=SubParser
        )
        sub.required = True

        # "add" sub-command
        add_parser = sub.add_parser("add", help="Add a device")
        add_parser.add_argument("hostname", help="Hostname of the device")
        add_parser.add_argument("--device-type", required=True, help="Device type")
        add_parser.add_argument(
            "--description", default=None, help="Device description"
        )
        add_parser.add_argument(
            "--offline",
            action="store_false",
            dest="online",
            default=True,
            help="Create the device offline (online by default)",
        )
        add_parser.add_argument(
            "--private",
            action="store_false",
            dest="public",
            default=True,
            help="Make the device private (public by default)",
        )
        add_parser.add_argument(
            "--worker", required=True, help="The name of the worker"
        )
        add_parser.add_argument(
            "--tags",
            nargs="*",
            required=False,
            help="List of tags to add to the device",
        )
        physical = add_parser.add_mutually_exclusive_group()
        physical.add_argument(
            "--physical-user",
            help="Username of the user with physical access to the device",
        )
        physical.add_argument(
            "--physical-group",
            help="Name of the group with physical access to the device",
        )
        owner = add_parser.add_mutually_exclusive_group()
        owner.add_argument(
            "--owner", help="Username of the user with ownership of the device"
        )
        owner.add_argument(
            "--group", help="Name of the group with ownership of the device"
        )

        # "copy" sub-command
        add_parser = sub.add_parser(
            "copy", help="Copy an existing device as a new hostname"
        )
        add_parser.add_argument("original", help="Hostname of the existing device")
        add_parser.add_argument("target", help="Hostname of the device to create")
        add_parser.add_argument(
            "--offline",
            action="store_false",
            dest="online",
            default=True,
            help="Create the device offline (online by default)",
        )
        add_parser.add_argument(
            "--private",
            action="store_false",
            dest="public",
            default=True,
            help="Make the device private (public by default)",
        )
        add_parser.add_argument(
            "--worker", required=True, help="The name of the worker (required)"
        )
        add_parser.add_argument(
            "--copy-with-tags",
            action="store_true",
            dest="copytags",
            default=False,
            help="Set all the tags of the original device on the target device",
        )

        # "details" sub-command
        details_parser = sub.add_parser("details", help="Details about a device")
        details_parser.add_argument("hostname", help="Hostname of the device")

        # "list" sub-command
        list_parser = sub.add_parser("list", help="List the installed devices")
        list_parser.add_argument(
            "--state",
            default=None,
            choices=["IDLE", "RESERVED", "RUNNING"],
            help="Show only devices with the given state",
        )
        health = list_parser.add_mutually_exclusive_group()
        health.add_argument(
            "--all",
            "-a",
            dest="show_all",
            default=None,
            action="store_true",
            help="Show all devices, including retired ones",
        )
        health.add_argument(
            "--health",
            default=None,
            choices=["GOOD", "UNKNOWN", "LOOPING", "BAD", "MAINTENANCE", "RETIRED"],
            help="Show only devices with the given health",
        )
        list_parser.add_argument(
            "--csv", dest="csv", default=False, action="store_true", help="Print as csv"
        )

        # "update" sub-command
        update_parser = sub.add_parser(
            "update", help="Update properties of the given device"
        )
        update_parser.add_argument("hostname", help="Hostname of the device")
        update_parser.add_argument(
            "--description", default=None, help="Set the description"
        )
        update_parser.add_argument(
            "--health",
            default=None,
            choices=["GOOD", "UNKNOWN", "LOOPING", "BAD", "MAINTENANCE", "RETIRED"],
            help="Update the device health",
        )
        update_parser.add_argument("--worker", default=None, help="Update the worker")
        display = update_parser.add_mutually_exclusive_group()
        display.add_argument(
            "--public", default=None, action="store_true", help="make the device public"
        )
        display.add_argument(
            "--private",
            dest="public",
            action="store_false",
            help="Make the device private",
        )
        physical = update_parser.add_mutually_exclusive_group()
        physical.add_argument(
            "--physical-user",
            help="Username of the user with physical access to the device",
        )
        physical.add_argument(
            "--physical-group",
            help="Name of the group with physical access to the device",
        )
        owner = update_parser.add_mutually_exclusive_group()
        owner.add_argument(
            "--owner", help="Username of the user with ownership of the device"
        )
        owner.add_argument(
            "--group",
            dest="group",
            help="Name of the group with ownership of the device",
        )

    def handle(self, *args, **options):
        """ Forward to the right sub-handler """
        if options["sub_command"] == "add":
            self.handle_add(options)
        elif options["sub_command"] == "copy":
            self.handle_copy(options)
        elif options["sub_command"] == "details":
            self.handle_details(options["hostname"])
        elif options["sub_command"] == "list":
            self.handle_list(
                options["state"], options["health"], options["show_all"], options["csv"]
            )
        else:
            self.handle_update(options)

    def _assign(
        self, name, device, physical=False, owner=False, user=False, group=False
    ):
        if user:
            try:
                user = User.objects.get(username=name)
            except User.DoesNotExist:
                raise CommandError("Unable to find user '%s'" % name)
            if physical:
                if device.physical_group:
                    device.physical_group = None
                device.physical_owner = user
            elif owner:
                if device.group:
                    device.group = None
                device.user = user
            else:
                raise CommandError("Invalid combination of options.")
        elif group:
            try:
                group = Group.objects.get(name=name)
            except Group.DoesNotExist:
                raise CommandError("Unable to find group '%s'" % name)
            if physical:
                if device.physical_owner:
                    device.physical_owner = None
                device.physical_group = group
            elif owner:
                if device.user:
                    device.user = None
                device.group = group
            else:
                raise CommandError("Invalid combination of options.")
        else:
            raise CommandError("Invalid combination of options.")

    def handle_add(self, options):
        hostname = options["hostname"]
        device_type = options["device_type"]
        worker_name = options["worker"]
        description = options["description"]
        public = options["public"]
        online = options["online"]
        tags = options["tags"]

        with contextlib.suppress(Device.DoesNotExist):
            Device.objects.get(hostname=hostname)
            raise CommandError("Device '%s' already exists" % hostname)

        try:
            dt = DeviceType.objects.get(name=device_type)
        except DeviceType.DoesNotExist:
            raise CommandError("Unable to find device-type '%s'" % device_type)

        try:
            worker = Worker.objects.get(hostname=worker_name)
        except Worker.DoesNotExist:
            raise CommandError("Unable to find worker '%s'" % worker_name)

        health = Device.HEALTH_GOOD if online else Device.HEALTH_MAINTENANCE
        device = Device.objects.create(
            hostname=hostname,
            device_type=dt,
            description=description,
            state=Device.STATE_IDLE,
            health=health,
            worker_host=worker,
        )

        if tags is not None:
            for tag in tags:
                device.tags.add(Tag.objects.get_or_create(name=tag)[0])

        if options["physical_user"]:
            self._assign(options["physical_user"], device, user=True, physical=True)
        elif options["physical_group"]:
            self._assign(options["physical_group"], device, group=True, physical=True)

        if options["owner"]:
            self._assign(options["owner"], device, user=True, owner=True)
        elif options["group"]:
            self._assign(options["group"], device, group=True, owner=True)
        device.save()

    def handle_copy(self, options):
        original = options["original"]
        target = options["target"]
        worker_name = options["worker"]
        public = options["public"]
        online = options["online"]
        tags = options["copytags"]

        try:
            from_device = Device.objects.get(hostname=original)
        except Device.DoesNotExist:
            raise CommandError("Original device '%s' does NOT exist!" % original)

        with contextlib.suppress(Device.DoesNotExist):
            Device.objects.get(hostname=target)
            raise CommandError("Target device '%s' already exists" % target)

        origin = from_device.load_configuration()
        if not origin:
            raise CommandError("Device dictionary does not exist for %s" % original)

        if online:
            target_dict = os.path.join(settings.DEVICES_PATH, "%s.jinja2" % target)
            if not os.path.exists(target_dict):
                raise CommandError(
                    "Refusing to copy %s to new device %s with health 'Good' -"
                    " no device dictionary exists for target device, yet. "
                    "Use --offline or copy %s.jinja2 to "
                    "/etc/lava-server/dispatcher-config/devices/ and try again."
                    % (original, target, target)
                )

        try:
            worker = Worker.objects.get(hostname=worker_name)
        except Worker.DoesNotExist:
            raise CommandError("Unable to find worker '%s'" % worker_name)

        health = Device.HEALTH_GOOD if online else Device.HEALTH_MAINTENANCE
        description = from_device.description
        device_type = from_device.device_type
        from_tags = None
        if tags:
            from_tags = from_device.tags.all()

        physical_owner = None
        physical_group = None
        owner = None
        group = None

        if from_device.physical_owner:
            physical_owner = from_device.physical_owner
        elif from_device.physical_group:
            physical_group = from_device.physical_group

        if from_device.owner:
            owner = from_device.owner
        elif from_device.group:
            group = from_device.group

        with transaction.atomic():
            device = Device.objects.create(
                hostname=target,
                device_type=device_type,
                description=description,
                state=Device.STATE_IDLE,
                health=health,
                worker_host=worker,
            )

            if from_tags is not None:
                for tag in from_tags:
                    device.tags.add(tag)

            if physical_owner:
                self._assign(physical_owner, device, user=True, physical=True)
            elif physical_group:
                self._assign(physical_group, device, group=True, physical=True)

            if owner:
                self._assign(owner, device, user=True, owner=True)
            elif group:
                self._assign(group, device, group=True, owner=True)

            device.save()

        destiny = device.load_configuration()
        if not destiny:
            print("Reminder: device dictionary does not yet exist for %s" % target)

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
        if device.user:
            owner = device.user.username
        elif device.group:
            owner = device.group.name
        else:
            owner = ""
        self.stdout.write("owner      : %s" % owner)

        if device.physical_owner:
            physical = device.physical_owner.username
        elif device.physical_group:
            physical = device.physical_group.name
        else:
            physical = ""
        self.stdout.write("physical   : %s" % physical)

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
                writer.writerow(
                    {
                        "hostname": device.hostname,
                        "device-type": device.device_type.name,
                        "state": device.get_state_display(),
                        "health": device.get_health_display(),
                    }
                )
        else:
            self.stdout.write("Available devices:")
            for device in devices:
                self.stdout.write(
                    "* %s (%s) %s, %s"
                    % (
                        device.hostname,
                        device.device_type.name,
                        device.get_state_display(),
                        device.get_health_display(),
                    )
                )

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

            if options["physical_user"]:
                self._assign(options["physical_user"], device, user=True, physical=True)
            elif options["physical_group"]:
                self._assign(
                    options["physical_group"], device, group=True, physical=True
                )

            if options["owner"]:
                self._assign(options["owner"], device, user=True, owner=True)
            elif options["group"]:
                self._assign(options["group"], device, group=True, owner=True)

            # Save the modifications
            device.save()
