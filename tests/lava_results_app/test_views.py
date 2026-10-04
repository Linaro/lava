# Copyright (C) 2026 Linaro Limited
#
# Author: Ben Copeland <ben.copeland@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from lava_results_app.models import (
    Chart,
    ChartQuery,
    Query,
    QueryCondition,
    QueryOmitResult,
    TestCase,
    TestSuite,
)
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


@pytest.fixture
def results_job(user):
    return TestJob.objects.create(submitter=user, is_public=True)


@pytest.fixture
def query(user):
    return Query.objects.create(
        name="q",
        owner=user,
        description="d",
        content_type=ContentType.objects.get_for_model(TestJob),
    )


@pytest.fixture
def chart(user):
    return Chart.objects.create(name="c", owner=user, description="d")


@pytest.fixture
def chart_query(chart, query):
    return ChartQuery.objects.create(chart=chart, query=query)


@pytest.fixture
def condition(query):
    return QueryCondition.objects.create(
        query=query,
        table=ContentType.objects.get_for_model(TestJob),
        field="id",
        operator="exact",
        value="1",
    )


@pytest.fixture
def omitted(query, results_job):
    # query_include_result removes an omission; it needs one to remove.
    return QueryOmitResult.objects.create(
        query=query,
        content_type=ContentType.objects.get_for_model(TestJob),
        object_id=results_job.id,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view,args",
    [
        ("lava.results.query_delete", ["user", "q"]),
        ("lava.results.query_toggle_published", ["user", "q"]),
        ("lava.results.query_refresh", ["user", "q"]),
        ("lava.results.query_omit_result", ["user", "q", 1]),
        ("lava.results.query_include_result", ["user", "q", 1]),
        ("lava.results.chart_delete", ["c"]),
        ("lava.results.chart_toggle_published", ["c"]),
        ("lava.results.chart_query_remove", ["c", 1]),
        ("lava.results.chart_omit_result", ["c", 1, 1]),
        ("lava.results.query_remove_condition", ["user", "q", 1]),
        ("chart_query_order_update", ["c"]),
        ("chart_settings_update", ["c", 1]),
    ],
)
def test_state_changing_results_views_reject_get(client, user, view, args):
    client.force_login(user)

    assert client.get(reverse(view, args=args)).status_code == 405


@pytest.mark.django_db
def test_state_changing_results_views_reject_anonymous_get(client):
    # @require_POST is the outermost decorator, so the method is rejected
    # before login_required can redirect: anonymous GETs get 405, not a login
    # page. Pinned deliberately.
    assert (
        client.get(reverse("lava.results.chart_delete", args=["c"])).status_code == 405
    )


# view -> how to build its args from the fixtures. Parametrised, so every case
# gets fresh fixtures: no endpoint depends on the previous one having run.
REDIRECTING_VIEWS = {
    "lava.results.query_toggle_published": lambda f: [
        f["user"].username,
        f["query"].name,
    ],
    "lava.results.query_delete": lambda f: [f["user"].username, f["query"].name],
    "lava.results.query_omit_result": lambda f: [
        f["user"].username,
        f["query"].name,
        f["results_job"].id,
    ],
    "lava.results.query_remove_condition": lambda f: [
        f["user"].username,
        f["query"].name,
        f["condition"].id,
    ],
    "lava.results.chart_toggle_published": lambda f: [f["chart"].name],
    "lava.results.chart_delete": lambda f: [f["chart"].name],
    "lava.results.chart_query_remove": lambda f: [f["chart"].name, f["chart_query"].id],
    "lava.results.chart_omit_result": lambda f: [
        f["chart"].name,
        f["chart_query"].id,
        f["results_job"].id,
    ],
}


@pytest.mark.django_db
@pytest.mark.parametrize("view", sorted(REDIRECTING_VIEWS))
def test_state_changing_results_views_accept_post(
    client, user, query, chart, chart_query, results_job, condition, view
):
    client.force_login(user)
    fixtures = {
        "user": user,
        "query": query,
        "chart": chart,
        "chart_query": chart_query,
        "results_job": results_job,
        "condition": condition,
    }
    response = client.post(reverse(view, args=REDIRECTING_VIEWS[view](fixtures)))
    assert response.status_code == 302


@pytest.mark.django_db
def test_query_include_result_accepts_post(client, user, query, results_job, omitted):
    # Needs an existing omission to include back, so it is its own case.
    client.force_login(user)
    response = client.post(
        reverse(
            "lava.results.query_include_result",
            args=[user.username, query.name, results_job.id],
        )
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_query_refresh_accepts_post(client, user, query):
    # JSON, not a redirect. On sqlite the refresh itself fails (view_exists
    # queries pg_class) and reports success=false, so pin the body shape
    # rather than its value.
    client.force_login(user)
    response = client.post(
        reverse("lava.results.query_refresh", args=[user.username, query.name])
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3 and isinstance(body[0], bool)


@pytest.mark.django_db
def test_chart_query_order_update_accepts_post(client, user, chart, chart_query):
    client.force_login(user)
    response = client.post(
        reverse("chart_query_order_update", args=[chart.name]),
        {"chart_query_order": str(chart_query.id)},
    )
    assert response.status_code == 200
    assert response.json() == "success"


@pytest.mark.django_db
def test_chart_settings_update_accepts_post(client, user, chart, chart_query):
    client.force_login(user)
    response = client.post(
        reverse("chart_settings_update", args=[chart.name, chart_query.id]),
        {"start_date": "2026-01-01", "is_legend_visible": "on", "is_delta": ""},
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_chart_list_remove_trigger_posts(client, user):
    # The view-side 405 is pinned above; this pins the chart-list table's
    # "remove" trigger: it must be a POST form, not a GET link.
    chart = Chart.objects.create(name="some-chart", owner=user)
    client.force_login(user)
    content = client.get(reverse("lava.results.chart_list")).content.decode()
    delete_url = reverse("lava.results.chart_delete", args=[chart.name])
    assert f'href="{delete_url}"' not in content
    assert f'action="{delete_url}" method="post"' in content
    # The form is only CSRF-safe if it carries the token; the default test
    # client skips CSRF enforcement, so pin the rendered input here.
    assert 'name="csrfmiddlewaretoken"' in content


@pytest.mark.django_db
def test_chart_delete_rejects_post_without_csrf_token(user):
    # CsrfViewMiddleware must be what protects the endpoint, not just the
    # method guard: a cross-site form POST with the session cookie but no
    # token must be refused.
    chart = Chart.objects.create(name="some-chart", owner=user)
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    response = csrf_client.post(reverse("lava.results.chart_delete", args=[chart.name]))
    assert response.status_code == 403


# Pages that carry state-changing triggers: page -> (page args, trigger URLs).
# The view-side 405s are pinned above; this pins the rendered templates, so
# reverting a trigger to a GET link fails here instead of breaking the UI
# silently. Covers the django-tables columns too (query_list, chart_list).
PAGES_WITH_TRIGGERS = {
    "lava.results.query_detail": (
        ["user", "q"],
        [
            ("lava.results.query_delete", ["user", "q"]),
            ("lava.results.query_toggle_published", ["user", "q"]),
        ],
    ),
    "lava.results.query_list": (
        [],
        [("lava.results.query_delete", ["user", "q"])],
    ),
    "lava.results.chart_detail": (
        ["c"],
        [
            ("lava.results.chart_delete", ["c"]),
            ("lava.results.chart_toggle_published", ["c"]),
        ],
    ),
}


@pytest.mark.django_db
@pytest.mark.parametrize("page", sorted(PAGES_WITH_TRIGGERS))
def test_results_pages_trigger_state_changes_by_post(client, user, query, chart, page):
    client.force_login(user)
    content = client.get(
        reverse(page, args=PAGES_WITH_TRIGGERS[page][0])
    ).content.decode()
    for action, args in PAGES_WITH_TRIGGERS[page][1]:
        url = reverse(action, args=args)
        assert f'href="{url}"' not in content, f"{page}: GET link to {action}"
        assert f'action="{url}" method="post"' in content, (
            f"{page}: no POST form for {action}"
        )
    assert 'name="csrfmiddlewaretoken"' in content, f"{page}: no CSRF token"
