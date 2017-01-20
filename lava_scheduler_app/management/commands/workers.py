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

from django.core.management.base import BaseCommand, CommandParser

from lava_scheduler_app.models import Worker


class Command(BaseCommand):
    help = "Manage workers"

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

        add_parser = sub.add_parser("add", help="Create a worker")
        add_parser.add_argument("--hostname", type=str, required=True,
                                help="Hostname of the worker")
        add_parser.add_argument("--description", type=str, default="",
                                help="Worker description")

        list_parser = sub.add_parser("list", help="List the workers")
        list_parser.add_argument("--all", default=False, action="store_true",
                                 help="Show all workers (including hidden ones)")
        list_parser.add_argument("--csv", dest="csv", default=False,
                                 action="store_true", help="Print as csv")

    def handle(self, *args, **options):
        """ Forward to the right sub-handler """
        if options["sub_command"] == "add":
            self.handle_add(options["hostname"], options["description"])
        elif options["sub_command"] == "list":
            self.handle_list(options["all"], options["csv"])

    def handle_add(self, hostname, description):
        Worker.objects.create(hostname=hostname,
                              description=description)

    def handle_list(self, show_all, format_as_csv):
        """ List the workers """
        workers = Worker.objects.all().order_by("hostname")
        # By default, do not show hidden workers
        if not show_all:
            workers = workers.filter(display=True)

        if format_as_csv:
            fields = ["hostname", "description", "master", "hidden", "devices"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for worker in workers:
                writer.writerow({
                    "hostname": worker.hostname,
                    "description": worker.description,
                    "master": worker.is_master,
                    "hidden": not worker.display,
                    "devices": worker.device_set.count()})
        else:
            self.stdout.write("Workers:")
            for worker in workers:
                string = "* %s (%d devices)"
                if worker.is_master:
                    string += " (master)"
                self.stdout.write(string % (worker.hostname, worker.device_set.count()))
