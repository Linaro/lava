# -*- coding: utf-8 -*-
# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from lava_common.compat import get_sub_parser_class


class Command(BaseCommand):
    help = "Update Django Site"

    def add_arguments(self, parser):
        SubParser = get_sub_parser_class(self)

        sub = parser.add_subparsers(
            dest="sub_command", help="Sub commands", parser_class=SubParser
        )
        sub.required = True

        list_parser = sub.add_parser("list", help="List the current Site")

        update_parser = sub.add_parser("update", help="Update site properties")
        update_parser.add_argument("--name", type=str, help="Display name of the Site")
        update_parser.add_argument(
            "--domain", type=str, default=None, help="site domain"
        )

    def handle(self, *args, **options):
        if options["sub_command"] == "list":
            self.handle_list()
        elif options["sub_command"] == "update":
            self.handle_update(options["name"], options["domain"])

    def handle_list(self):
        """ List the current Site """
        site = Site.objects.get_current()
        self.stdout.write("Site:")
        self.stdout.write("\tDomain: %s" % site.domain)
        self.stdout.write("\tName: %s" % site.name)

    def handle_update(self, name, domain):
        """ Update Site properties """
        site = Site.objects.get_current()
        site.domain = domain
        site.name = name
        site.save()
