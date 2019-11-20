# -*- coding: utf-8 -*-
# Copyright (C) 2018 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

from django.conf.urls import include, url

from lava_rest_app.base.views import LavaObtainAuthToken
from . import versions
from lava_rest_app.base.routers import router as router_v01
from lava_rest_app.v02.routers import router as router_v02


urlpatterns = [
    url(r"^(?P<version>(v0.1))/", include(router_v01.urls)),
    url(r"^(?P<version>(v0.2))/", include(router_v02.urls)),
    url(
        r"^^(?P<version>(%s))/token/" % versions.urlpattern(),
        LavaObtainAuthToken.as_view(),
    ),
]
