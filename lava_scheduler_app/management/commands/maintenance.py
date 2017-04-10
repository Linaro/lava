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

import logging
import sys

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from lava_scheduler_app.models import Device, TestJob


class Command(BaseCommand):
    help = "Switch to maintenance mode"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", default=False,
                            help="Force maintenance by canceling all running jobs")
        parser.add_argument("--dry-run", action="store_true", default=False,
                            help="Simulate the execution (rollback the transaction)")
        parser.add_argument("--user", type=str, default="lava-health",
                            help="Username of the current admin")

    def handle(self, *args, **options):
        # Disable the internal loggers
        logging.getLogger('dispatcher-master').disabled = True
        logging.getLogger('lava_scheduler_app').disabled = True
        # Find the user
        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            self.stderr.write("User '%s' does not exist" % options["user"])
            self.stdout.write("A valid user is needed to store the state transitions")
            sys.exit(1)
        # Use an explicit transaction that we can rollback if needed
        transaction.set_autocommit(False)

        self.stdout.write("Setting all devices to maintenance mode:")
        devices = Device.objects.exclude(status=Device.OFFLINE) \
                                .exclude(status=Device.RETIRED) \
                                .order_by("hostname")
        for device in devices:
            # Print the device hostname only if it has been put OFFLINE
            if device.put_into_maintenance_mode(user, "Maintenance", None):
                self.stdout.write("* %s" % device.hostname)

        if options["force"]:
            self.stdout.write("Cancel all running jobs")
            testjobs = TestJob.objects.filter(status=TestJob.RUNNING)
            for testjob in testjobs:
                self.stdout.write("* %d" % testjob.id)
                testjob.cancel(user)

        if options["dry_run"]:
            self.stdout.write("Rollback the changes")
            transaction.rollback()
        else:
            self.stdout.write("Commit the changes")
            transaction.commit()
