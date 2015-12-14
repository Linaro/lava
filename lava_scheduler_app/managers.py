# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.

from django.db import models
from django.db.models import Q

from django_restricted_resource.managers import RestrictedResourceQuerySet

from lava_scheduler_app import utils


class RestrictedTestJobQuerySet(RestrictedResourceQuerySet):

    def visible_by_user(self, user):

        from lava_scheduler_app.models import TestJob
        # Legacy jobs.
        conditions_legacy = Q(is_pipeline=False)
        if not user or user.is_anonymous():
            conditions_legacy &= Q(is_public=True)
        elif not user.is_superuser and not user.has_perm('lava_scheduler_app.cancel_resubmit_testjob'):
            # continue adding conditions only if user is not superuser and
            # does not have admin permission for jobs.
            conditions_legacy &= (Q(is_public=True) |
                                  Q(user=user) |
                                  Q(submitter=user) |
                                  Q(group__in=user.groups.all()))

        # Pipeline jobs.
        conditions = Q(is_pipeline=True)
        if not user or user.is_anonymous():
            conditions_legacy &= Q(is_public=True)
        elif not user.is_superuser and not user.has_perm('lava_scheduler_app.cancel_resubmit_testjob') and not user.has_perm('lava_scheduler_app.change_device'):
            # continue adding conditions only if user is not superuser and
            # does not have admin permission for jobs or devices.
            conditions &= (
                Q(is_public=True) |
                Q(submitter=user) |
                (~Q(actual_device=None) & Q(actual_device__user=user)) |
                Q(visibility=TestJob.VISIBLE_PUBLIC) |
                Q(visibility=TestJob.VISIBLE_PERSONAL, submitter=user) |
                # NOTE: this supposedly does OR and we need user to be in
                # all the visibility groups if we allow multiple groups in
                # field viewing groups.
                Q(visibility=TestJob.VISIBLE_GROUP,
                  viewing_groups__in=user.groups.all())
            )

        conditions |= conditions_legacy
        queryset = self.filter(conditions)

        return queryset


class RestrictedTestCaseQuerySet(RestrictedResourceQuerySet):

    def visible_by_user(self, user):

        from lava_scheduler_app.models import TestJob
        jobs = TestJob.objects.filter(
            testsuite__testcase__in=self).visible_by_user(user)

        return self.filter(suite__job__in=jobs)


class RestrictedTestSuiteQuerySet(models.QuerySet):

    def visible_by_user(self, user):

        from lava_scheduler_app.models import TestJob
        jobs = TestJob.objects.filter(testsuite__in=self).visible_by_user(user)

        return self.filter(job__in=jobs)
