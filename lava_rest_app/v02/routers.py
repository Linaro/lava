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

from lava_server.compat import drf_basename

# FIXME: remove when drf-extensions 0.7 is uploaded to debian.
from django.db.models.sql import datastructures
from django.core.exceptions import EmptyResultSet

datastructures.EmptyResultSet = EmptyResultSet

from rest_framework_extensions.routers import ExtendedDefaultRouter
from . import views


router = ExtendedDefaultRouter()
router.register(r"aliases", views.AliasViewSet)
router.register(r"devices", views.DeviceViewSet)
router.register(r"devicetypes", views.DeviceTypeViewSet)
jobs_router = router.register(r"jobs", views.TestJobViewSet)
jobs_router.register(
    r"tests",
    views.TestCaseViewSet,
    parents_query_lookups=["suite__job_id"],
    **drf_basename("jobs-tests"),
)
jobs_router.register(
    r"suites",
    views.TestSuiteViewSet,
    parents_query_lookups=["job_id"],
    **drf_basename("jobs-suite"),
).register(
    r"tests",
    views.TestCaseViewSet,
    parents_query_lookups=["suite__job_id", "suite_id"],
    **drf_basename("suites-test"),
)
router.register(r"permissions/devicetypes", views.GroupDeviceTypePermissionViewSet)
router.register(r"permissions/devices", views.GroupDevicePermissionViewSet)
router.register(r"system", views.SystemViewSet, **drf_basename("system"))
router.register(r"tags", views.TagViewSet)
router.register(r"workers", views.WorkerViewSet)
