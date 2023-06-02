# Copyright (C) 2018 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.conf.urls import include

from lava_rest_app.base.routers import router as router_v01
from lava_rest_app.base.views import LavaObtainAuthToken
from lava_rest_app.v02.routers import router as router_v02
from lava_server.compat import url

from . import versions

urlpatterns = [
    url(r"^(?P<version>(v0.1))/", include(router_v01.urls)),
    url(r"^(?P<version>(v0.2))/", include(router_v02.urls)),
    url(
        r"^^(?P<version>(%s))/token/" % versions.urlpattern(),
        LavaObtainAuthToken.as_view(),
    ),
]
