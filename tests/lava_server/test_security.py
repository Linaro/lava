# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from lava_server.security import LavaRequireLoginPathsMiddleware
from linaro_django_xmlrpc.models import AuthToken


def _middleware():
    return LavaRequireLoginPathsMiddleware(lambda request: HttpResponse("ok"))


def _request(path, **extra):
    request = RequestFactory().get(path, **extra)
    request.user = AnonymousUser()
    return request


def test_non_gated_path_passes_for_anonymous(settings):
    settings.REQUIRE_LOGIN_PATHS = ["results/query"]
    response = _middleware()(_request("/scheduler/"))
    assert response.content == b"ok"


def test_gated_path_redirects_anonymous_to_login(settings):
    settings.REQUIRE_LOGIN_PATHS = ["results/query"]
    response = _middleware()(_request("/results/query"))
    assert response.status_code == 302
    assert response.url.startswith(settings.LOGIN_URL)


def test_gated_prefix_covers_subpaths(settings):
    settings.REQUIRE_LOGIN_PATHS = ["results/query"]
    response = _middleware()(_request("/results/query/~admin/some-query"))
    assert response.status_code == 302


def test_gated_path_passes_authenticated_user(db, django_user_model, settings):
    settings.REQUIRE_LOGIN_PATHS = ["results/query"]
    request = _request("/results/query")
    request.user = django_user_model.objects.create_user(username="tester")
    response = _middleware()(request)
    assert response.content == b"ok"


def test_gated_api_path_passes_with_valid_token(db, django_user_model, settings):
    settings.REQUIRE_LOGIN_PATHS = ["api"]
    user = django_user_model.objects.create_user(username="tester")
    AuthToken.objects.create(user=user, secret="secretkey")  # nosec - unit test
    response = _middleware()(
        _request("/api/v0.2/jobs/", HTTP_AUTHORIZATION="Token secretkey")
    )
    assert response.content == b"ok"


def test_gated_api_path_redirects_without_token(settings):
    settings.REQUIRE_LOGIN_PATHS = ["api"]
    response = _middleware()(_request("/api/v0.2/jobs/"))
    assert response.status_code == 302


def test_exempt_paths_stay_open(settings):
    settings.REQUIRE_LOGIN_PATHS = ["v1"]
    response = _middleware()(_request("/v1/healthz"))
    assert response.content == b"ok"


def test_installed_middleware_gates_query_list(db, django_user_model, settings, client):
    settings.REQUIRE_LOGIN_PATHS = ["results/query"]
    settings.MIDDLEWARE = settings.MIDDLEWARE + [
        "lava_server.security.LavaRequireLoginPathsMiddleware"
    ]
    url = reverse("lava.results.query_list")

    response = client.get(url)
    assert response.status_code == 302
    assert response.url.startswith(settings.LOGIN_URL)

    client.force_login(django_user_model.objects.create_user(username="tester"))
    response = client.get(url)
    assert response.status_code == 200
