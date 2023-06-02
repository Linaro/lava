# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
    basename="jobs-tests",
)
jobs_router.register(
    r"suites",
    views.TestSuiteViewSet,
    parents_query_lookups=["job_id"],
    basename="jobs-suite",
).register(
    r"tests",
    views.TestCaseViewSet,
    parents_query_lookups=["suite__job_id", "suite_id"],
    basename="suites-test",
)
router.register(r"permissions/devicetypes", views.GroupDeviceTypePermissionViewSet)
router.register(r"permissions/devices", views.GroupDevicePermissionViewSet)
router.register(r"system", views.SystemViewSet, basename="system")
router.register(r"tags", views.TagViewSet)
router.register(r"workers", views.WorkerViewSet)
