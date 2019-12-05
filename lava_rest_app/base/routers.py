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

import warnings

from lava_rest_app.base import views as base_views

from rest_framework import routers, views
from rest_framework.response import Response


# django-rest-framework from Debian stretch (v3.8.2) does not provide this
# class.
# Manually backport the class from a recent version
try:
    from rest_framework.routers import APIRootView
except ImportError:
    warnings.warn("Remove once the stretch support is dropped.", DeprecationWarning)
    from collections import OrderedDict
    from django.urls import NoReverseMatch, reverse

    class APIRootView(views.APIView):
        """
        The default basic root view for DefaultRouter
        """

        _ignore_model_permissions = True
        schema = None  # exclude from schema
        api_root_dict = None

        def get(self, request, *args, **kwargs):
            # Return a plain {"name": "hyperlink"} response.
            ret = OrderedDict()
            namespace = request.resolver_match.namespace
            for key, url_name in self.api_root_dict.items():
                if namespace:
                    url_name = namespace + ":" + url_name
                try:
                    ret[key] = reverse(
                        url_name,
                        args=args,
                        kwargs=kwargs,
                        request=request,
                        format=kwargs.get("format", None),
                    )
                except NoReverseMatch:
                    # Don't bail out if eg. no list routes exist, only detail routes.
                    continue

            return Response(ret)


class LavaApiRootView(APIRootView):
    pass


class API(routers.DefaultRouter):
    APIRootView = LavaApiRootView


router = API()
router.register(r"devices", base_views.DeviceViewSet)
router.register(r"devicetypes", base_views.DeviceTypeViewSet)
router.register(r"jobs", base_views.TestJobViewSet)
router.register(r"workers", base_views.WorkerViewSet)
