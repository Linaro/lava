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

import datetime
import re
from shutil import rmtree
import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.utils import timezone

from lava_scheduler_app.models import (
    TestJob
)


class Command(BaseCommand):
    help = "Manage jobs"

    job_status = {
        "SUBMITTED": TestJob.SUBMITTED,
        "RUNNING": TestJob.RUNNING,
        "COMPLETE": TestJob.COMPLETE,
        "INCOMPLETE": TestJob.INCOMPLETE,
        "CANCELED": TestJob.CANCELED,
        "CANCELING": TestJob.CANCELING
    }

    def add_arguments(self, parser):
        cmd = self

        class SubParser(CommandParser):
            """
            Sub-parsers constructor that mimic Django constructor.
            See http://stackoverflow.com/a/37414551
            """
            def __init__(self, **kwargs):
                super(SubParser, self).__init__(cmd, **kwargs)

        sub = parser.add_subparsers(dest="sub_command", help="Sub commands",
                                    parser_class=SubParser)
        sub.required = True

        rm = sub.add_parser("rm", help="Remove selected jobs. Keep in mind "
                                       "that v1 bundles won't be removed, "
                                       "leading to strange behavior when "
                                       "browsing the bundle pages.")
        rm.add_argument("--older-than", default=None, type=str,
                        help="Remove jobs older than this. The time is of the "
                             "form: 1h (one hour) or 2d (two days). "
                             "By default, all jobs will be removed.")
        rm.add_argument("--status", default=None,
                        choices=["SUBMITTED", "RUNNING", "COMPLETE",
                                 "INCOMPLETE", "CANCELED", "CANCELING"],
                        help="Filter by job status")
        rm.add_argument("--submitter", default=None, type=str,
                        help="Filter jobs by submitter")
        rm.add_argument("--dry-run", default=False, action="store_true",
                        help="Do not remove any data, simulate the output")
        rm.add_argument("--v1", default=False, action="store_true",
                        help="Remove only v1 jobs. "
                             "If this is the only filtering option, all v1 jobs will be removed.")
        rm.add_argument("--slow", default=False, action="store_true",
                        help="Be nice with the system by sleeping regularly")

    def handle(self, *_, **options):
        """ forward to the right sub-handler """
        if options["sub_command"] == "rm":
            self.handle_rm(options["older_than"], options["submitter"],
                           options["status"], options["v1"],
                           options["dry_run"], options["slow"])

    def handle_rm(self, older_than, submitter, status, v1_only, simulate, slow):
        if not older_than and not submitter and not status and not v1_only:
            raise CommandError("You should specify at least one filtering option")

        if simulate:
            transaction.set_autocommit(False)

        jobs = TestJob.objects.all().order_by('id')
        if older_than is not None:
            pattern = re.compile("^(?P<time>\d+)(?P<unit>(h|d))$")
            match = pattern.match(older_than)
            if match is None:
                raise CommandError("Invalid older-than format")

            if match.groupdict()["unit"] == "d":
                delta = datetime.timedelta(days=int(match.groupdict()["time"]))
            else:
                delta = datetime.timedelta(hours=int(match.groupdict()["time"]))
            jobs = jobs.filter(end_time__lt=(timezone.now() - delta))

        if submitter is not None:
            try:
                user = User.objects.get(username=submitter)
            except User.DoesNotExist:
                raise CommandError("Unable to find submitter '%s'" % submitter)
            jobs = jobs.filter(submitter=user)

        if status is not None:
            jobs = jobs.filter(status=self.job_status[status])

        if v1_only:
            jobs = jobs.filter(is_pipeline=False)

        self.stdout.write("Removing %d jobs:" % jobs.count())
        counter = 0
        for job in jobs:
            self.stdout.write("* %d (%s): %s" % (job.id, job.end_time, job.output_dir))
            try:
                if not simulate:
                    rmtree(job.output_dir)
            except OSError as exc:
                self.stderr.write("  -> Unable to remove the directory: %s" % str(exc))
            job.delete()
            counter += 1
            if slow and not counter % 100:
                self.stdout.write("sleeping 2s...")
                time.sleep(2)

        if simulate:
            transaction.rollback()
