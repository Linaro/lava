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

import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from lava_scheduler_app.models import Device, TestJob


class Command(BaseCommand):
    help = "Switch to maintenance mode"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Force maintenance by canceling all running jobs",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simulate the execution (rollback the transaction)",
        )
        parser.add_argument(
            "--user",
            type=str,
            default="lava-health",
            help="Username of the current admin",
        )

    def handle(self, *args, **options):
        # Disable the internal loggers
        logging.getLogger("lava-master").disabled = True
        logging.getLogger("lava_scheduler_app").disabled = True
        # Find the user
        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            self.stdout.write("A valid user is needed to store the state transitions")
            raise CommandError("User '%s' does not exist" % options["user"])
        # Use an explicit transaction that we can rollback if needed
        transaction.set_autocommit(False)

        self.stdout.write("Setting all devices to maintenance mode:")
        devices = (
            Device.objects.exclude(health=Device.HEALTH_MAINTENANCE)
            .exclude(health=Device.HEALTH_RETIRED)
            .order_by("hostname")
        )
        for device in devices:
            prev_health = device.get_health_display()
            device.health = Device.HEALTH_MAINTENANCE
            device.log_admin_entry(
                user, "%s → %s (cmdline)" % (prev_health, device.get_health_display())
            )
            device.save()
            self.stdout.write("* %s" % device.hostname)

        if options["force"]:
            self.stdout.write("Cancel all running jobs")
            testjobs = TestJob.objects.filter(status=TestJob.RUNNING)
            for testjob in testjobs:
                self.stdout.write("* %d" % testjob.id)
                testjob.cancel(user)

        if options["dry_run"]:
            self.stdout.write("Roll back changes")
            transaction.rollback()
        else:
            self.stdout.write("Commit the changes")
            transaction.commit()
