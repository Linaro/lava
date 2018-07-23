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

    job_state = {
        "SUBMITTED": TestJob.STATE_SUBMITTED,
        "SCHEDULING": TestJob.STATE_SCHEDULING,
        "SCHEDULED": TestJob.STATE_SCHEDULED,
        "RUNNING": TestJob.STATE_RUNNING,
        "CANCELING": TestJob.STATE_CANCELING,
        "FINISHED": TestJob.STATE_FINISHED
    }

    def add_arguments(self, parser):
        cmd = self

        class SubParser(CommandParser):
            """
            Sub-parsers constructor that mimic Django constructor.
            See http://stackoverflow.com/a/37414551
            """
            def __init__(self, **kwargs):
                super().__init__(cmd, **kwargs)

        sub = parser.add_subparsers(dest="sub_command", help="Sub commands",
                                    parser_class=SubParser)
        sub.required = True

        fail = sub.add_parser("fail", help="Force the job status in the database. Keep "
                                           "in mind that any corresponding lava-run "
                                           "process will NOT be stopped by this operation.")
        fail.add_argument("job_id", help="job id", type=int)

        rm = sub.add_parser("rm", help="Remove selected jobs. Keep in mind "
                                       "that v1 bundles won't be removed, "
                                       "leading to strange behavior when "
                                       "browsing the bundle pages.")
        rm.add_argument("--older-than", default=None, type=str,
                        help="Remove jobs older than this. The time is of the "
                             "form: 1h (one hour) or 2d (two days). "
                             "By default, all jobs will be removed.")
        rm.add_argument("--state", default=None,
                        choices=["SUBMITTED", "SCHEDULING", "SCHEDULED", "RUNNING", "CANCELING",
                                 "FINISHED"],
                        help="Filter by job state")
        rm.add_argument("--submitter", default=None, type=str,
                        help="Filter jobs by submitter")
        rm.add_argument("--dry-run", default=False, action="store_true",
                        help="Do not remove any data, simulate the output")
        rm.add_argument("--slow", default=False, action="store_true",
                        help="Be nice with the system by sleeping regularly")

    def handle(self, *_, **options):
        """ forward to the right sub-handler """
        if options["sub_command"] == "rm":
            self.handle_rm(options["older_than"], options["submitter"],
                           options["state"], options["dry_run"], options["slow"])
        elif options["sub_command"] == "fail":
            self.handle_fail(options["job_id"])

    def handle_fail(self, job_id):
        try:
            with transaction.atomic():
                job = TestJob.objects.select_for_update().get(pk=job_id)
                job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
                job.save()
        except TestJob.DoesNotExist:
            raise CommandError("TestJob '%d' does not exists" % job_id)

    def handle_rm(self, older_than, submitter, state, simulate, slow):
        if not older_than and not submitter and not state:
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

        if state is not None:
            jobs = jobs.filter(state=self.job_state[state])

        self.stdout.write("Removing %d jobs:" % jobs.count())

        while True:
            count = 0
            for job in jobs[0:100]:
                count += 1
                self.stdout.write("* %d (%s): %s" % (job.id, job.end_time, job.output_dir))
                try:
                    if not simulate:
                        rmtree(job.output_dir)
                except OSError as exc:
                    self.stderr.write("  -> Unable to remove the directory: %s" % str(exc))
                job.delete()

            if count == 0:
                break
            if slow:
                self.stdout.write("sleeping 2s...")
                time.sleep(2)

        if simulate:
            transaction.rollback()
