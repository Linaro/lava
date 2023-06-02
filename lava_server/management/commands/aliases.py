# Copyright (C) 2019 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from lava_scheduler_app.models import Alias, DeviceType


class Command(BaseCommand):
    help = "Manage aliases"

    def add_arguments(self, parser):
        sub = parser.add_subparsers(
            dest="sub_command",
            help="Sub commands",
        )
        sub.required = True

        # "add" sub-command
        add_parser = sub.add_parser("add", help="Add alias to an existing device type")
        add_parser.add_argument("alias", help="Alias to add to device type")
        add_parser.add_argument("devicetype", help="Device type")

        # "list" sub-command
        list_parser = sub.add_parser("list", help="List Aliases")

        # "show" sub-command
        show_parser = sub.add_parser(
            "show", help="Show all aliases for an existing device type"
        )
        show_parser.add_argument("alias", help="Alias to display details about")

        # "remove" sub-command
        remove_parser = sub.add_parser("remove", help="Remove alias from device type")
        remove_parser.add_argument("alias", help="Alias to remove from device type")

    def handle(self, *args, **options):
        """Forward to the right sub-handler"""
        if options["sub_command"] == "add":
            self.handle_add(options)
        if options["sub_command"] == "list":
            self.handle_list(options)
        elif options["sub_command"] == "show":
            self.handle_show(options)
        elif options["sub_command"] == "remove":
            self.handle_remove(options)

    def handle_add(self, options):
        devicetype = options["devicetype"]
        alias_name = options["alias"]
        try:
            device_type = DeviceType.objects.get(name=devicetype)
            _, created = Alias.objects.get_or_create(
                name=alias_name, device_type=device_type
            )
            if not created:
                raise CommandError("Alias '%s' already exists!" % alias_name)
        except DeviceType.DoesNotExist:
            raise CommandError("Device '%s' does NOT exist!" % devicetype)
        except IntegrityError:
            raise CommandError("Alias '%s' already exists!" % alias_name)

    def handle_list(self, options):
        self.stdout.write("Aliases:")
        for alias in Alias.objects.all():
            self.stdout.write("* %s: %s" % (alias.name, alias.device_type.name))

    def handle_show(self, options):
        alias_name = options["alias"]
        try:
            alias = Alias.objects.get(name=alias_name)
            self.stdout.write("device_type: %s" % alias.device_type.name)
        except Alias.DoesNotExist:
            raise CommandError("Alias '%s' does NOT exist!" % alias_name)

    def handle_remove(self, options):
        alias_name = options["alias"]
        try:
            Alias.objects.get(name=alias_name).delete()
        except Alias.DoesNotExist:
            raise CommandError("Alias '%s' does NOT exist!" % alias_name)
