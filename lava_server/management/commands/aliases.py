# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
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

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import IntegrityError
from django.utils.version import get_version

from lava_scheduler_app.models import DeviceType, Alias


class Command(BaseCommand):
    help = "Manage aliases"

    def add_arguments(self, parser):
        cmd = self

        class SubParser(CommandParser):
            """
            Sub-parsers constructor that mimic Django constructor.
            See http://stackoverflow.com/a/37414551
            """

            def __init__(self, **kwargs):
                if get_version() >= "2":
                    super().__init__(**kwargs)
                else:
                    super().__init__(cmd, **kwargs)

        sub = parser.add_subparsers(
            dest="sub_command", help="Sub commands", parser_class=SubParser
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
        """ Forward to the right sub-handler """
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
