# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from lava_results_app.models import TestCase, TestSet, TestSuite
from lava_scheduler_app.models import TestJob

if TYPE_CHECKING:
    from django.core.management.base import CommandParser
    from django.db.models import QuerySet


class Command(BaseCommand):
    help = "Check database uniqueness and remove violating entities."

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Remove non-unique entities without asking.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List number of non-unique entities instead of deleting.",
        )

    def handle(self, *args, yes: bool, dry_run: bool, **kwargs):
        self.stderr.write("Checking TestJobs with duplicated sub_id...")
        duplicated_sub_id_query = TestJob.objects.filter(~Q(sub_id="")).filter(
            sub_id__in=(
                TestJob.objects.values("sub_id")
                .annotate(
                    sub_ids_count=Count(
                        "*",
                    )
                )
                .filter(sub_ids_count__gt=1)
                .values("sub_id")
            ),
        )
        self.handle_duplicates(duplicated_sub_id_query, yes, dry_run)

        self.stderr.write("Checking TestJobs with duplicated TestSets...")
        duplicated_testset_query = TestJob.objects.filter(
            pk__in=(
                TestSuite.objects.values("job_id").filter(
                    pk__in=(
                        TestSet.objects.values("suite_id", "name")
                        .annotate(suite_cases=Count("*"))
                        .filter(suite_cases__gt=1)
                        .values("suite_id")
                    )
                )
            ),
        )
        self.handle_duplicates(duplicated_testset_query, yes, dry_run)

        self.stderr.write("Checking TestJobs with duplicated TestSuites...")
        duplicated_testsuites_query = TestJob.objects.filter(
            pk__in=(
                TestJob.objects.values("pk", "testsuite__name")
                .annotate(
                    test_suite_names=Count(
                        "*",
                    )
                )
                .filter(test_suite_names__gt=1)
                .values("pk")
            ),
        )
        self.handle_duplicates(duplicated_testsuites_query, yes, dry_run)

        self.stderr.write("Checking TestJobs with duplicated lava job TestCases...")
        duplicated_testcases_query = TestJob.objects.filter(
            pk__in=(
                TestSuite.objects.values("job_id").filter(
                    pk__in=(
                        TestCase.objects.filter(name="job")
                        .values("suite_id", "name")
                        .annotate(job_cases=Count("*"))
                        .filter(job_cases__gt=1)
                        .values("suite_id")
                    )
                )
            ),
        )
        self.handle_duplicates(duplicated_testcases_query, yes, dry_run)

    def handle_duplicates(self, query: QuerySet, yes: bool, dry_run: bool):
        entity_count = 0
        for entity in query:
            self.stderr.write(self.style.NOTICE(f"Found: {repr(entity)}"))
            entity_count += 1
            if dry_run:
                continue

            if yes or (input("Delete? yes/[no]: ").lower() == "yes"):
                entity.delete()
                self.stderr.write(self.style.SUCCESS(f"Deleted: {repr(entity)}"))
            else:
                self.stderr.write(self.style.SUCCESS(f"Skipped: {repr(entity)}"))

        if entity_count:
            self.stderr.write(self.style.NOTICE(f"Found {entity_count} entities."))
        else:
            self.stderr.write(self.style.SUCCESS("No entities found."))
