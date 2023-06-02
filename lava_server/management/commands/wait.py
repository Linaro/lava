# Copyright (C) 2020 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import time
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Wait for services"

    def add_arguments(self, parser):
        parser.add_argument(
            "service", type=str, choices=["database", "migrations"], help="the service"
        )
        parser.add_argument(
            "--delay", type=int, default=1, help="delay between retries"
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
                try:
                    connections["default"].cursor().execute(
                        "SELECT * from django_migrations"
                    )
                    break
                except OperationalError:
                    self.stdout.write(". (database connection closed)")
                    connections["default"].close()
                else:
                    self.stdout.write(".")
            time.sleep(delay)
        self.stdout.write("[done]")
        self.stdout.write("Waiting for migrations:")
        while True:
            with contextlib.suppress(Exception):
                try:
                    stdout = StringIO()
                    call_command("showmigrations", plan=True, stdout=stdout)
                    stdout.seek(0, 0)
                    if all(["[ ]" not in line for line in stdout.readlines()]):
                        break
                except OperationalError:
                    self.stdout.write(". (database connection closed)")
                    connections["default"].close()
                else:
                    self.stdout.write(".")
            time.sleep(delay)
        self.stdout.write("[done]")
