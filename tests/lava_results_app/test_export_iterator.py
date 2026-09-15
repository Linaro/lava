# Copyright (C) 2026 Linaro Limited
#
# Author: Ben Copeland <ben.copeland@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import patch

import pytest
from django.db.models import QuerySet
from django.urls import reverse

from lava_results_app.models import TestCase, TestSuite
from lava_scheduler_app.models import TestJob, User


@pytest.mark.django_db
@pytest.mark.parametrize("extension", ["csv", "yaml"])
def test_job_export_does_not_cache_results(
    client, mocker, django_assert_num_queries, extension
):
    user = User.objects.create_user("user")
    job = TestJob.objects.create(submitter=user, is_public=True)
    for suite_name in ["first", "second"]:
        suite = TestSuite.objects.create(job=job, name=suite_name)
        for result in TestCase.RESULT_REVERSE:
            TestCase.objects.create(
                suite=suite,
                name=f'case {result}, "quoted"\n café',
                result=result,
                measurement="12.345" if result == TestCase.RESULT_PASS else None,
                units="ms",
                metadata="level: 1.2\nvalues: [one, two]\n",
                start_log_line=10,
                end_log_line=20,
            )

    url = reverse(f"lava.results.testjob_{extension}", args=[job.id])
    with patch.object(QuerySet, "iterator", QuerySet.__iter__):
        original = client.get(url)
        expected = b"".join(original.streaming_content)

    select_related = mocker.spy(QuerySet, "select_related")
    response = client.get(url)
    queryset = select_related.spy_return

    assert response.status_code == 200
    assert response.streaming
    assert dict(response.headers) == dict(original.headers)
    assert queryset.model is TestCase
    assert queryset._result_cache is None
    with django_assert_num_queries(1):
        content = b"".join(response.streaming_content)
    assert content == expected
    assert queryset._result_cache is None
