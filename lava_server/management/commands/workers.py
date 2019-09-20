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

import contextlib
import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from lava_scheduler_app.models import Worker
from lava_server.compat import get_sub_parser_class


class Command(BaseCommand):
    help = "Manage workers"

    def add_arguments(self, parser):
        SubParser = get_sub_parser_class(self)

        sub = parser.add_subparsers(
            dest="sub_command", help="Sub commands", parser_class=SubParser
        )
        sub.required = True

        add_parser = sub.add_parser("add", help="Create a worker")
        add_parser.add_argument("hostname", type=str, help="Hostname of the worker")
        add_parser.add_argument(
            "--description", type=str, default="", help="Worker description"
        )
        add_parser.add_argument(
            "--health",
            type=str,
            default="ACTIVE",
            choices=["ACTIVE", "MAINTENANCE", "RETIRED"],
            help="Worker health",
        )

        details_parser = sub.add_parser("details", help="Details of a worker")
        details_parser.add_argument("hostname", type=str, help="Hostname of the worker")
        details_parser.add_argument(
            "--devices",
            action="store_true",
            default=False,
            help="Print the list of attached devices",
        )

        list_parser = sub.add_parser("list", help="List the workers")
        list_parser.add_argument(
            "-a",
            "--all",
            default=False,
            action="store_true",
            help="Show all workers (including retired ones)",
        )
        list_parser.add_argument(
            "--csv", dest="csv", default=False, action="store_true", help="Print as csv"
        )

        update_parser = sub.add_parser("update", help="Update worker properties")
        update_parser.add_argument("hostname", type=str, help="Hostname of the worker")
        update_parser.add_argument(
            "--description", type=str, default=None, help="Worker description"
        )
        update_parser.add_argument(
            "--health",
            type=str,
            default=None,
            choices=["ACTIVE", "MAINTENANCE", "RETIRED"],
            help="Set worker health",
        )

    def handle(self, *args, **options):
        """ Forward to the right sub-handler """
        if options["sub_command"] == "add":
            self.handle_add(
                options["hostname"], options["description"], options["health"]
            )
        elif options["sub_command"] == "details":
            self.handle_details(options["hostname"], options["devices"])
        elif options["sub_command"] == "list":
            self.handle_list(options["all"], options["csv"])
        elif options["sub_command"] == "update":
            self.handle_update(
                options["hostname"], options["description"], options["health"]
            )

    def handle_add(self, hostname, description, health_str):
        """ Create a worker """
        with contextlib.suppress(Worker.DoesNotExist):
            Worker.objects.get(hostname=hostname)
            raise CommandError("Worker already exists with hostname %s" % hostname)

        if health_str == "ACTIVE":
            health = Worker.HEALTH_ACTIVE
        elif health_str == "MAINTENANCE":
            health = Worker.HEALTH_MAINTENANCE
        else:
            health = Worker.HEALTH_RETIRED
        Worker.objects.create(hostname=hostname, description=description, health=health)

    def handle_details(self, hostname, print_devices):
        try:
            worker = Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise CommandError("Unable to find worker '%s'" % hostname)

        self.stdout.write("hostname   : %s" % hostname)
        self.stdout.write("state      : %s" % worker.get_state_display())
        self.stdout.write("health     : %s" % worker.get_health_display())
        self.stdout.write("description: %s" % worker.description)
        if not print_devices:
            self.stdout.write("devices    : %d" % worker.device_set.count())
        else:
            self.stdout.write("devices    :")
            for device in worker.device_set.order_by("hostname"):
                self.stdout.write("- %s" % device.hostname)

    def handle_list(self, show_all, format_as_csv):
        """ List the workers """
        workers = Worker.objects.all().order_by("hostname")
        # By default, do not show hidden workers
        if not show_all:
            workers = workers.exclude(health=Worker.HEALTH_RETIRED)

        if format_as_csv:
            fields = ["hostname", "description", "master", "state", "health", "devices"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for worker in workers:
                writer.writerow(
                    {
                        "hostname": worker.hostname,
                        "description": worker.description,
                        "state": worker.get_state_display(),
                        "health": worker.get_health_display(),
                        "devices": worker.device_set.count(),
                    }
                )
        else:
            self.stdout.write("Workers:")
            for worker in workers:
                self.stdout.write(
                    "* %s (%d devices)" % (worker.hostname, worker.device_set.count())
                )

    def handle_update(self, hostname, description, health):
        """ Update worker properties """
        with transaction.atomic():
            try:
                worker = Worker.objects.select_for_update().get(hostname=hostname)
            except Worker.DoesNotExist:
                raise CommandError("No worker exists with hostname %s" % hostname)

            if description is not None:
                worker.description = description
            if health is not None:
                if health == "ACTIVE":
                    worker.go_health_active()
                elif health == "MAINTENANCE":
                    worker.go_health_maintenance()
                else:
                    worker.go_health_retired()
            worker.save()
