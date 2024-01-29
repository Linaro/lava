# Copyright (C) 2018 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.conf.urls import include
from django.urls import re_path

from lava_rest_app.v02.routers import router as router_v02
from lava_rest_app.v02.views import LavaObtainAuthToken
from lava_rest_app.v03.routers import router as router_v03

from . import versions

urlpatterns = [
    re_path(r"^(?P<version>(v0.2))/", include(router_v02.urls)),
    re_path(r"^(?P<version>(v0.3))/", include(router_v03.urls)),
    re_path(
        r"^^(?P<version>(%s))/token/" % versions.urlpattern(),
        LavaObtainAuthToken.as_view(),
    ),
]
