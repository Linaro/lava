# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from rest_framework import routers
from rest_framework.routers import APIRootView

from lava_rest_app.base import views as base_views


class LavaApiRootView(APIRootView):
    pass


class API(routers.DefaultRouter):
    APIRootView = LavaApiRootView


router = API()
router.register(r"devices", base_views.DeviceViewSet)
router.register(r"devicetypes", base_views.DeviceTypeViewSet)
router.register(r"jobs", base_views.TestJobViewSet)
router.register(r"workers", base_views.WorkerViewSet)
