# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
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

from lava_rest_app.base import views as base_views

from rest_framework import routers
from rest_framework.routers import APIRootView


class LavaApiRootView(APIRootView):
    pass


class API(routers.DefaultRouter):
    APIRootView = LavaApiRootView


router = API()
router.register(r"devices", base_views.DeviceViewSet)
router.register(r"devicetypes", base_views.DeviceTypeViewSet)
router.register(r"jobs", base_views.TestJobViewSet)
router.register(r"workers", base_views.WorkerViewSet)
