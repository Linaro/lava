# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

import inspect
import re

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import URLResolver, reverse

from lava_scheduler_app.models import RemoteArtifactsAuth
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


# View/action names implying the endpoint changes state.
MUTATING_NAME = re.compile(
    r"(?:^|_)(?:delete|cancel|fail|omit|include|toggle|remove|resubmit"
    r"|publish|update|refresh|abort|reset|annotate|set|change)(?:$|_)"
)
# Decorators or inline checks that restrict the accepted HTTP method.
# Plain text match over the source block. A comment or string mentioning
# request.method would falsely pass; upgrade to AST inspection of the
# decorator list if this ever bites.
METHOD_GUARD = re.compile(r"require_POST|require_http_methods|request\.method")


def _iter_patterns(patterns):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _iter_patterns(pattern.url_patterns)
        else:
            yield pattern


def _iter_callbacks():
    """Yield (url_name, callback) for every routed endpoint."""
    from django.conf import settings

    urlconf = __import__(settings.ROOT_URLCONF, {}, {}, [""])
    for pattern in _iter_patterns(urlconf.urlpatterns):
        yield pattern.name or str(pattern.pattern), pattern.callback


def test_mutating_function_views_have_method_guard():
    violations = []
    for name, callback in _iter_callbacks():
        if getattr(callback, "cls", None) is not None:
            continue  # class-based view: covered by the REST action test below
        unwrapped = inspect.unwrap(callback)
        if unwrapped.__module__.startswith("django.contrib."):
            continue  # admin/auth views dispatch methods themselves
        if not MUTATING_NAME.search(unwrapped.__name__):
            continue
        if getattr(callback, "csrf_exempt", False):
            # POST-only is not CSRF-safe without the token check
            violations.append(f"{name} (csrf_exempt)")
            continue
        try:
            source = inspect.getsource(unwrapped)
        except OSError:  # pragma: no cover
            continue
        if not METHOD_GUARD.search(source):
            violations.append(name)
    assert not violations, f"state-changing GET-able views: {violations}"


def test_mutating_rest_actions_are_post_only():
    violations = []
    seen = set()
    for _, callback in _iter_callbacks():
        view_cls = getattr(callback, "cls", None)
        if view_cls is None or view_cls in seen:
            continue
        seen.add(view_cls)
        # dir(), not vars(): actions inherited from a base viewset must be
        # checked too.
        for method_name in dir(view_cls):
            method = getattr(view_cls, method_name, None)
            mapping = getattr(method, "mapping", None)
            if mapping is None or not MUTATING_NAME.search(method.__name__):
                continue
            if "get" in mapping or "head" in mapping:
                violations.append(f"{view_cls.__name__}.{method.__name__}")
    assert not violations, f"state-changing GET-able REST actions: {violations}"


@pytest.mark.django_db
def test_token_delete_trigger_posts(client, django_user_model):
    # me.html's token-delete trigger must be a CSRF-tokened POST form, never a
    # GET link; the view-side 405 is pinned by the guards above.
    user = django_user_model.objects.create_user(username="token-owner")
    token = RemoteArtifactsAuth.objects.create(user=user, name="n1", token="v1")
    client.force_login(user)
    content = client.get(reverse("lava.me")).content.decode()
    delete_url = reverse("lava.delete_remote_auth", args=[token.pk])
    assert f'href="{delete_url}"' not in content
    assert f'action="{delete_url}" method="post"' in content
    assert 'name="csrfmiddlewaretoken"' in content
