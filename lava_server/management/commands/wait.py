# -*- coding: utf-8 -*-
# Copyright (C) 2020 Linaro Limited
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
from io import StringIO
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Wait for services"

    def add_arguments(self, parser):
        parser.add_argument(
            "service", type=str, choices=["database", "migrations"], help="the service"
        )
        parser.add_argument(
            "--delay", type=int, default=5, help="delay between retries"
        )

    def handle(self, *args, **options):
        if options["service"] == "database":
            self.wait_database(options["delay"])
        elif options["service"] == "migrations":
            self.wait_migrations(options["delay"])

    def wait_database(self, delay):
        self.stdout.write("Waiting for the database:")
        while True:
            with contextlib.suppress(Exception):
                connections["default"].cursor()
                break
            self.stdout.write(".")
            time.sleep(delay)
        self.stdout.write("[done]")

    def wait_migrations(self, delay):
        self.stdout.write("Waiting for migration table:")
        while True:
            with contextlib.suppress(Exception):
                connections["default"].cursor().execute(
                    "SELECT * from django_migrations"
                )
                break
            self.stdout.write(".")
            time.sleep(delay)
        self.stdout.write("[done]")
        self.stdout.write("Waiting for migrations:")
        while True:
            stdout = StringIO()
            call_command("showmigrations", plan=True, stdout=stdout)
            stdout.seek(0, 0)
            if all(["[ ]" not in line for line in stdout.readlines()]):
                break
            self.stdout.write(".")
            time.sleep(delay)
        self.stdout.write("[done]")
