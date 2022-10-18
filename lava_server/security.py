# Copyright (C) 2022 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
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
from __future__ import annotations

from base64 import b64decode
from pathlib import PurePosixPath
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.decorators import login_required

from linaro_django_xmlrpc.models import AuthToken


class LavaRequireLoginMiddleware:
    HOME_PATH: ClassVar[PurePosixPath] = PurePosixPath("/") / settings.MOUNT_POINT
    LOGIN_PATH: ClassVar[PurePosixPath] = PurePosixPath(settings.LOGIN_URL)
    # Token authenticated paths
    XMLRPC_PATH: ClassVar[PurePosixPath] = HOME_PATH / "RPC2"
    REST_API_PATH: ClassVar[PurePosixPath] = HOME_PATH / "api"

    SCHEDULER_INTERNALS_PATH: ClassVar[PurePosixPath] = (
        HOME_PATH / "scheduler/internal/v1"
    )
    OIDC_PATH: ClassVar[PurePosixPath] = HOME_PATH / "oidc"

    def __init__(self, get_response):
        self.get_response = get_response
        self.require_login = login_required(get_response)

    @classmethod
    def is_login_not_required(cls, path: PurePosixPath) -> bool:
        if path == cls.HOME_PATH:
            return True

        if path == cls.LOGIN_PATH:
            return True

        try:
            path.relative_to(cls.SCHEDULER_INTERNALS_PATH)
        except ValueError:
            ...
        else:
            return True

        if settings.OIDC_ENABLED:
            try:
                path.relative_to(cls.OIDC_PATH)
            except ValueError:
                ...
            else:
                return True

        return False

    @classmethod
    def is_token_authenticated_path(cls, path: PurePosixPath) -> bool:
        try:
            path.relative_to(cls.XMLRPC_PATH)
        except ValueError:
            ...
        else:
            return True

        try:
            path.relative_to(cls.REST_API_PATH)
        except ValueError:
            ...
        else:
            return True

        return False

    @classmethod
    def passthrough_valid_token(cls, auth_header: str) -> bool:
        if not auth_header:
            return False

        try:
            auth_method, auth_value = auth_header.split()
        except ValueError:
            return False

        if auth_method.lower() == "token":
            token_str = auth_value
        elif auth_method.lower() == "basic":
            # HACK: lavacli sends token as a password of basic auth
            try:
                basic_auth_decoded = b64decode(auth_value).decode("utf-8")
            except UnicodeDecodeError:
                return False

            try:
                _, token_str = basic_auth_decoded.split(":")
            except ValueError:
                return False
        else:
            return False

        try:
            token_object = AuthToken.objects.select_related("user").get(
                secret=token_str
            )
        except AuthToken.DoesNotExist:
            return False

        if not token_object.user.is_active:
            return False

        return True

    def __call__(self, request):
        path = PurePosixPath(request.path)

        if self.is_login_not_required(path):
            return self.get_response(request)

        if self.is_token_authenticated_path(path) and self.passthrough_valid_token(
            request.META.get("HTTP_AUTHORIZATION", "")
        ):
            return self.get_response(request)

        return self.require_login(request)
