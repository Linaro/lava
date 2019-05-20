# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
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


from django.contrib.auth.backends import ModelBackend

from lava_scheduler_app.auth import PermissionAuth
from lava_scheduler_app.models import TestJob, Device, DeviceType


def is_object_supported(obj):
    """
    Returns True if obj is supported. False if obj is None or not supported.
    """
    return (
        isinstance(obj, TestJob)
        or isinstance(obj, Device)
        or isinstance(obj, DeviceType)
    )


class GroupPermissionBackend(ModelBackend):
    def authenticate(self, username, password):
        return None

    def has_perm(self, user, perm, obj=None):
        """
        Returns True if given user has particular permission for the object.
        If no object is given, False is returned.
        """
        if not is_object_supported(obj):
            return False

        app_label, _ = perm.split(".", maxsplit=1)
        if app_label != obj._meta.app_label:
            raise ValueError("Passed perm has wrong app label: '%s'" % app_label)

        auth = PermissionAuth(user)
        return auth.has_perm(perm, obj)

    def get_all_permissions(self, user, obj=None):
        """
        Returns a set of permissions that the given user has for object.
        """
        if not is_object_supported(obj):
            return set()

        auth = PermissionAuth(user)
        return auth.get_perms(obj)
