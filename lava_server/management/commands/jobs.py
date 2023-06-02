# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import datetime
import lzma
import pathlib
import re
import time
from shutil import chown, rmtree

import voluptuous
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from lava_common.schemas import validate
from lava_common.yaml import yaml_safe_load
from lava_scheduler_app.models import TestJob


def _create_output_size(base, size):
    (base / "output.yaml.size").write_text(str(size), encoding="utf-8")
    with contextlib.suppress(PermissionError):
        chown(str(base / "output.yaml.size"), "lavaserver", "lavaserver")


class Command(BaseCommand):
    help = "Manage jobs"

    job_state = {
        "SUBMITTED": TestJob.STATE_SUBMITTED,
        "SCHEDULING": TestJob.STATE_SCHEDULING,
        "SCHEDULED": TestJob.STATE_SCHEDULED,
        "RUNNING": TestJob.STATE_RUNNING,
        "CANCELING": TestJob.STATE_CANCELING,
        "FINISHED": TestJob.STATE_FINISHED,
    }

    def add_arguments(self, parser):
        sub = parser.add_subparsers(
            dest="sub_command",
            help="Sub commands",
        )
        sub.required = True

        fail = sub.add_parser(
            "fail",
            help="Force the job status in the database. Keep "
            "in mind that any corresponding lava-run "
            "process will NOT be stopped by this operation.",
        )
        fail.add_argument("job_id", help="job id", type=int)

        list_p = sub.add_parser("list", help="List jobs")
        list_p.add_argument(
            "--lxc", default=False, action="store_true", help="Only list lxc jobs"
        )
        list_p.add_argument(
            "--newer-than",
            default=None,
            type=str,
            help="List jobs newer than this. The time is of the "
            "form: 1h (one hour) or 2d (two days). ",
        )

        list_p.add_argument(
            "--state",
            default=None,
            choices=[
                "SUBMITTED",
                "SCHEDULING",
                "SCHEDULED",
                "RUNNING",
                "CANCELING",
                "FINISHED",
            ],
            help="Filter by job state",
        )
        list_p.add_argument(
            "--submitter", default=None, type=str, help="Filter jobs by submitter"
        )
        list_p.add_argument(
            "--no-submitter",
            default=None,
            type=str,
            help="Filter out jobs by submitter",
        )

        rm = sub.add_parser(
            "rm",
            help="Remove selected jobs. Keep in mind "
            "that v1 bundles won't be removed, "
            "leading to strange behavior when "
            "browsing the bundle pages.",
        )
        rm.add_argument(
            "--older-than",
            default=None,
            type=str,
            help="Remove jobs older than this. The time is of the "
            "form: 1h (one hour) or 2d (two days). "
            "By default, all jobs will be removed.",
        )
        rm.add_argument(
            "--submitter", default=None, type=str, help="Filter jobs by submitter"
        )
        rm.add_argument(
            "--dry-run",
            default=False,
            action="store_true",
            help="Do not remove any data, simulate the output",
        )
        rm.add_argument(
            "--slow",
            default=False,
            action="store_true",
            help="Be nice with the system by sleeping regularly",
        )

        valid = sub.add_parser(
            "validate",
            help="Validate selected historical jobs against the current schema. ",
        )
        valid.add_argument(
            "--mail-admins",
            action="store_true",
            default=False,
            help="Send a mail to the admins with a list of failing jobs",
        )
        valid.add_argument(
            "--submitter", default=None, type=str, help="Filter jobs by submitter"
        )
        valid.add_argument(
            "--newer-than",
            default="1d",
            type=str,
            help="Validate jobs newer than this. The time is of the "
            "form: 1h (one hour) or 2d (two days). "
            "By default, only jobs in the last 24 hours will be validated.",
        )
        valid.add_argument(
            "--strict",
            default=False,
            action="store_true",
            help="If set to True, the validator will reject any extra keys "
            "that are present in the job definition but not defined in the schema",
        )

        comp = sub.add_parser("compress", help="Compress the corresponding job logs")
        comp.add_argument(
            "--newer-than",
            default=None,
            type=str,
            help="Compress jobs newer than this. The time is of the "
            "form: 1h (one hour) or 2d (two days). "
            "By default, all jobs will be compressed.",
        )
        comp.add_argument(
            "--older-than",
            default=None,
            type=str,
            help="Compress jobs older than this. The time is of the "
            "form: 1h (one hour) or 2d (two days). "
            "By default, all jobs logs will be compressed.",
        )
        comp.add_argument(
            "--submitter", default=None, type=str, help="Filter jobs by submitter"
        )
        comp.add_argument(
            "--dry-run",
            default=False,
            action="store_true",
            help="Do not compress any logs, simulate the output",
        )
        comp.add_argument(
            "--slow",
            default=False,
            action="store_true",
            help="Be nice with the system by sleeping regularly",
        )

    def handle(self, *_, **options):
        """forward to the right sub-handler"""
        if options["sub_command"] == "list":
            self.handle_list(
                options["lxc"],
                options["newer_than"],
                options["state"],
                options["submitter"],
                options["no_submitter"],
            )
        elif options["sub_command"] == "rm":
            self.handle_rm(
                options["older_than"],
                options["submitter"],
                options["dry_run"],
                options["slow"],
            )
        elif options["sub_command"] == "fail":
            self.handle_fail(options["job_id"])
        elif options["sub_command"] == "validate":
            self.handle_validate(
                options["newer_than"],
                options["submitter"],
                options["strict"],
                options["mail_admins"],
            )
        elif options["sub_command"] == "compress":
            self.handle_compress(
                options["older_than"],
                options["newer_than"],
                options["submitter"],
                options["dry_run"],
                options["slow"],
            )

    def handle_fail(self, job_id):
        try:
            with transaction.atomic():
                job = TestJob.objects.select_for_update().get(pk=job_id)
                job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
                job.save()
        except TestJob.DoesNotExist:
            raise CommandError("TestJob '%d' does not exists" % job_id)

    def handle_list(self, lxc, newer_than, state, submitter, no_submitter):
        jobs = TestJob.objects.all().order_by("-id")
        if submitter is not None:
            try:
                user = User.objects.get(username=submitter)
            except User.DoesNotExist:
                raise CommandError("Unable to find submitter '%s'" % submitter)
            jobs = jobs.filter(submitter=user)

        if no_submitter is not None:
            try:
                user = User.objects.get(username=no_submitter)
            except User.DoesNotExist:
                raise CommandError("Unable to find submitter '%s'" % no_submitter)
            jobs = jobs.exclude(submitter=user)

        if newer_than is not None:
            pattern = re.compile(r"^(?P<time>\d+)(?P<unit>(h|d))$")
            match = pattern.match(newer_than)
            if match is None:
                raise CommandError("Invalid newer-than format")

            if match.groupdict()["unit"] == "d":
                delta = datetime.timedelta(days=int(match.groupdict()["time"]))
            else:
                delta = datetime.timedelta(hours=int(match.groupdict()["time"]))
            jobs = jobs.filter(end_time__gt=(timezone.now() - delta))

        if state is not None:
            jobs = jobs.filter(state=self.job_state[state])

        print("Listing jobs:")
        for job in jobs:
            to_print = not lxc
            if lxc:
                if "protocols:" in job.definition and "lava-lxc:" in job.definition:
                    data = yaml_safe_load(job.definition)
                    if data.get("protocols", {}).get("lava-lxc") is not None:
                        to_print = True

            if to_print:
                print(
                    f"* {job.submit_time} - {job.id}@{job.submitter} - {job.description}"
                )

    def handle_rm(self, older_than, submitter, simulate, slow):
        if not older_than and not submitter:
            raise CommandError("You should specify at least one filtering option")

        if simulate:
            transaction.set_autocommit(False)

        jobs = TestJob.objects.all().order_by("id")
        jobs = jobs.filter(state=TestJob.STATE_FINISHED)

        if older_than is not None:
            pattern = re.compile(r"^(?P<time>\d+)(?P<unit>(h|d))$")
            match = pattern.match(older_than)
            if match is None:
                raise CommandError("Invalid older-than format")

            if match.groupdict()["unit"] == "d":
                delta = datetime.timedelta(days=int(match.groupdict()["time"]))
            else:
                delta = datetime.timedelta(hours=int(match.groupdict()["time"]))
            jobs = jobs.filter(
                Q(end_time__lt=(timezone.now() - delta))
                | Q(end_time__isnull=True, submit_time__lt=(timezone.now() - delta))
            )

        if submitter is not None:
            try:
                user = User.objects.get(username=submitter)
            except User.DoesNotExist:
                raise CommandError("Unable to find submitter '%s'" % submitter)
            jobs = jobs.filter(submitter=user)

        self.stdout.write("Removing %d jobs:" % jobs.count())

        media_root = pathlib.Path(settings.MEDIA_ROOT)
        while True:
            count = 0
            for job in jobs[0:100]:
                count += 1
                self.stdout.write(
                    "* %d (%s): %s" % (job.id, job.end_time, job.output_dir)
                )
                try:
                    if not simulate:
                        rmtree(job.output_dir)
                        # delete parents directories (if empty)
                        with contextlib.suppress(OSError, ValueError):
                            for parent in pathlib.Path(job.output_dir).parents:
                                parent.relative_to(media_root)
                                if parent == media_root:
                                    break
                                parent.rmdir()
                                self.stdout.write("  -> rmdir %s" % (parent))
                except OSError as exc:
                    self.stderr.write(
                        "  -> Unable to remove the directory: %s" % str(exc)
                    )
                job.delete()

            if count == 0:
                break
            if slow:
                self.stdout.write("sleeping 2s...")
                time.sleep(2)

        if simulate:
            transaction.rollback()

    def handle_validate(self, newer_than, submitter, strict, should_mail_admins):
        jobs = TestJob.objects.all().order_by("id")
        if newer_than is not None:
            pattern = re.compile(r"^(?P<time>\d+)(?P<unit>(h|d))$")
            match = pattern.match(newer_than)
            if match is None:
                raise CommandError("Invalid newer-than format")

            if match.groupdict()["unit"] == "d":
                delta = datetime.timedelta(days=int(match.groupdict()["time"]))
            else:
                delta = datetime.timedelta(hours=int(match.groupdict()["time"]))
            jobs = jobs.filter(end_time__gt=(timezone.now() - delta))

        if submitter is not None:
            try:
                user = User.objects.get(username=submitter)
            except User.DoesNotExist:
                raise CommandError("Unable to find submitter '%s'" % submitter)
            jobs = jobs.filter(submitter=user)

        invalid = {}
        for job in jobs:
            if job.is_multinode:
                definition = job.multinode_definition
            else:
                definition = job.original_definition
            data = yaml_safe_load(definition)
            try:
                validate(data, strict, settings.EXTRA_CONTEXT_VARIABLES)
                print("* %s" % job.id)
            except voluptuous.Invalid as exc:
                invalid[job.id] = {
                    "submitter": job.submitter,
                    "dt": job.requested_device_type,
                    "key": exc.path,
                    "msg": exc.msg,
                }
                print("* %s Invalid job definition" % job.id)
                print("    submitter: %s" % job.submitter)
                print("    device-type: %s" % job.requested_device_type)
                print("    key: %s" % exc.path)
                print("    msg: %s" % exc.msg)
        if invalid:
            if should_mail_admins:
                body = "Hello,\n\nthe following jobs schema are invalid:\n"
                for job_id in invalid.keys():
                    body += "* %s\n" % job_id
                    body += "  submitter: {submitter}\n  device-type: {dt}\n  key: {key}\n  msg: {msg}\n".format(
                        **invalid[job_id]
                    )
                body += "\n-- \nlava-server manage jobs validate"
                mail_admins("Invalid jobs", body)
            raise CommandError("Some jobs are invalid")

    def handle_compress(self, older_than, newer_than, submitter, simulate, slow):
        if not older_than and not newer_than and not submitter:
            raise CommandError("You should specify at least one filtering option")

        jobs = TestJob.objects.all().order_by("id").filter(state=TestJob.STATE_FINISHED)
        if older_than is not None:
            pattern = re.compile(r"^(?P<time>\d+)(?P<unit>(h|d))$")
            match = pattern.match(older_than)
            if match is None:
                raise CommandError("Invalid older-than format")

            if match.groupdict()["unit"] == "d":
                delta = datetime.timedelta(days=int(match.groupdict()["time"]))
            else:
                delta = datetime.timedelta(hours=int(match.groupdict()["time"]))
            jobs = jobs.filter(end_time__lt=(timezone.now() - delta))

        if newer_than is not None:
            pattern = re.compile(r"^(?P<time>\d+)(?P<unit>(h|d))$")
            match = pattern.match(newer_than)
            if match is None:
                raise CommandError("Invalid newer-than format")

            if match.groupdict()["unit"] == "d":
                delta = datetime.timedelta(days=int(match.groupdict()["time"]))
            else:
                delta = datetime.timedelta(hours=int(match.groupdict()["time"]))
            jobs = jobs.filter(end_time__gt=(timezone.now() - delta))

        if submitter is not None:
            try:
                user = User.objects.get(username=submitter)
            except User.DoesNotExist:
                raise CommandError("Unable to find submitter '%s'" % submitter)
            jobs = jobs.filter(submitter=user)

        # Only job.id, job.end_time, job.output_dir are used
        # job.output_dir uses job.submit_time
        jobs = jobs.values("pk", "end_time", "submit_time")
        # Loop on all jobs
        for index, job_data in enumerate(jobs.iterator(chunk_size=100)):
            job = TestJob(**job_data)
            base = pathlib.Path(job.output_dir)
            if not (base / "output.yaml").exists():
                if (base / "output.yaml.size").exists():
                    self.stdout.write(
                        "* %d (%s): %s [SKIP]" % (job.id, job.end_time, job.output_dir)
                    )
                elif (base / "output.yaml.xz").exists():
                    self.stdout.write(
                        "* %d (%s): %s [create size file]"
                        % (job.id, job.end_time, job.output_dir)
                    )
                    if not simulate:
                        with contextlib.suppress(FileNotFoundError):
                            with lzma.open(str(base / "output.yaml.xz"), "rb") as f_in:
                                _create_output_size(base, f_in.seek(0, 2))
                continue

            self.stdout.write("* %d (%s): %s" % (job.id, job.end_time, job.output_dir))
            try:
                if not simulate:
                    # Read the logs
                    data = (base / "output.yaml").read_bytes()
                    # Save the uncompressed size for later use
                    _create_output_size(base, len(data))
                    # Compresse the logs
                    with lzma.open(str(base / "output.yaml.xz"), "wb") as f_out:
                        f_out.write(data)
                    with contextlib.suppress(PermissionError):
                        chown(str(base / "output.yaml.xz"), "lavaserver", "lavaserver")
                    # Remove the original file
                    (base / "output.yaml").unlink()
            except OSError as exc:
                self.stderr.write("  -> Unable to compress the logs: %s" % str(exc))

            if slow and index % 100 == 99:
                self.stdout.write("sleeping 2s...")
                time.sleep(2)

        self.stdout.write(f"Compressed {index+1} jobs.")
