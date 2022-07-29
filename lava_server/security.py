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

from pathlib import PurePosixPath
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.decorators import login_required


class LavaRequireLoginMiddleware:
    HOME_PATH: ClassVar[PurePosixPath] = PurePosixPath("/") / settings.MOUNT_POINT
    LOGIN_PATH: ClassVar[PurePosixPath] = PurePosixPath(settings.LOGIN_URL)

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

    def __call__(self, request):
        path = PurePosixPath(request.path)

        if self.is_login_not_required(path):
            return self.get_response(request)

        return self.require_login(request)
