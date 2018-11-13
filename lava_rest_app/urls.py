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

from . import api
from . import versions

urlpatterns = [
    url(r"^(?P<version>(%s))/" % versions.urlpattern(), include(api.router.urls)),
    url(
        r"^^(?P<version>(%s))/token/" % versions.urlpattern(),
        api.LavaObtainAuthToken.as_view(),
    ),
]
