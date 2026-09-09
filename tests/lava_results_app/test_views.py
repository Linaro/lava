# Copyright (C) 2026 Linaro Limited
#
# Author: Ben Copeland <ben.copeland@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from lava_results_app.models import TestCase, TestSuite
from lava_scheduler_app.models import TestJob, User


@pytest.fixture
def user():
    return User.objects.create_user("user")


@pytest.fixture
def old_public_testcase(user):
    job = TestJob.objects.create(submitter=user, is_public=True)
    TestJob.objects.filter(pk=job.pk).update(
        submit_time=timezone.now() - timedelta(days=90)
    )
    suite = TestSuite.objects.create(job=job, name="suite")
    return TestCase.objects.create(
        suite=suite, name="case", result=TestCase.RESULT_PASS
    )


@pytest.fixture
def private_testcase(user):
    job = TestJob.objects.create(submitter=user, is_public=False)
    suite = TestSuite.objects.create(job=job, name="suite")
    return TestCase.objects.create(
        suite=suite, name="case", result=TestCase.RESULT_PASS
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view", ["lava.results.testcase", "lava.results.testcase_yaml"]
)
def test_outside_public_job_window_costs_one_query(
    client, settings, old_public_testcase, django_assert_num_queries, view
):
    settings.PUBLIC_JOB_WINDOW_DAYS = 30

    with django_assert_num_queries(1):
        response = client.get(reverse(view, args=[old_public_testcase.id]))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view", ["lava.results.testcase", "lava.results.testcase_yaml"]
)
def test_inside_public_job_window_is_visible(
    client, settings, old_public_testcase, view
):
    settings.PUBLIC_JOB_WINDOW_DAYS = 365

    response = client.get(reverse(view, args=[old_public_testcase.id]))

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view", ["lava.results.testcase", "lava.results.testcase_yaml"]
)
def test_private_job_forbidden_for_anonymous(client, private_testcase, view):
    response = client.get(reverse(view, args=[private_testcase.id]))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view", ["lava.results.testcase", "lava.results.testcase_yaml"]
)
def test_private_job_visible_to_submitter(client, user, private_testcase, view):
    client.force_login(user)

    response = client.get(reverse(view, args=[private_testcase.id]))

    assert response.status_code == 200
