# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib

from django.core.management.base import BaseCommand, CommandError

from lava_scheduler_app.models import Device, Tag


class Command(BaseCommand):
    help = "Manage device tags"

    def add_arguments(self, parser):
        sub = parser.add_subparsers(
            dest="sub_command",
            help="Sub commands",
        )
        sub.required = True

        # "add" sub-command
        add_parser = sub.add_parser(
            "add", help="Add one or more existing device tag(s) to an existing device"
        )
        add_parser.add_argument("hostname", help="Hostname of the device")
        add_parser.add_argument(
            "--tags",
            nargs="*",
            required=False,
            help="List of tags to add to the device",
        )

        # "show" sub-command
        show_parser = sub.add_parser(
            "show", help="Show all device tag(s) for an existing device"
        )
        show_parser.add_argument("hostname", help="Hostname of the device")

        # "list" sub-command
        sub.add_parser("list", help="List all device tag(s)")

        # "remove" sub-command
        remove_parser = sub.add_parser(
            "remove",
            help="Remove one or more existing device tag(s) from an existing device",
        )
        remove_parser.add_argument("hostname", help="Hostname of the device")
        remove_parser.add_argument(
            "--tags",
            nargs="*",
            required=False,
            help="List of tags to remove from the device",
        )

        # "create" sub-command
        create_parser = sub.add_parser("create", help="Create a new device tag")
        create_parser.add_argument("name", help="Name of the new tag")
        create_parser.add_argument("description", help="Description of the new tag")

    def handle(self, *args, **options):
        """Forward to the right sub-handler"""
        if options["sub_command"] == "add":
            self.handle_add(options)
        elif options["sub_command"] == "list":
            self.handle_list(options)
        elif options["sub_command"] == "show":
            self.handle_show(options)
        elif options["sub_command"] == "remove":
            self.handle_remove(options)
        else:
            self.handle_create(options)

    def handle_add(self, options):
        hostname = options["hostname"]
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise CommandError("Device '%s' does NOT exist!" % hostname)

        tags = options["tags"]
        if tags is not None:
            for tag in tags:
                try:
                    tag = Tag.objects.get(name=tag)
                except Tag.DoesNotExist:
                    raise CommandError("Tag '%s' does NOT exist!" % tag)
                device.tags.add(tag)
        device.save()

    def handle_show(self, options):
        hostname = options["hostname"]
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise CommandError("Device '%s' does NOT exist!" % hostname)
        if device.tags.all():
            self.stdout.write("Hostname: %s" % hostname)
        for tag in device.tags.all():
            self.stdout.write(
                "Tag name: '%s' Description: '%s'" % (tag.name, tag.description)
            )

    def handle_remove(self, options):
        hostname = options["hostname"]
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise CommandError("Device '%s' does NOT exist!" % hostname)

        tags = options["tags"]
        if tags is not None:
            for tag in tags:
                try:
                    tag = Tag.objects.get(name=tag)
                except Device.DoesNotExist:
                    raise CommandError("Tag '%s' does NOT exist!" % tag)
                if tag not in device.tags.all():
                    raise CommandError(
                        "Device %s does not have tag %s" % (hostname, tag.name)
                    )
                device.tags.remove(tag)
        device.save()

    def handle_create(self, options):
        name = options["name"]
        description = options["description"]

        with contextlib.suppress(Tag.DoesNotExist):
            Tag.objects.get(name=name)
            raise CommandError("Tag '%s' already exists" % name)
        Tag.objects.create(name=name, description=description)

    def handle_list(self, options):
        for tag in Tag.objects.all():
            self.stdout.write(
                "Name: '%s' Description: '%s'" % (tag.name, tag.description)
            )
