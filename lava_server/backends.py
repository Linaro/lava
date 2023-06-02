# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from django.contrib.auth.backends import ModelBackend

from lava_scheduler_app.auth import PermissionAuth
from lava_scheduler_app.models import Device, DeviceType, Worker


def is_object_supported(obj):
    """
    Returns True if obj is supported. False if obj is None or not supported.
    """
    return (
        isinstance(obj, Device)
        or isinstance(obj, DeviceType)
        or isinstance(obj, Worker)
    )


class GroupPermissionBackend(ModelBackend):
    def authenticate(self, username, password):
        return None

    def has_perm(self, user, perm, obj=None):
        if hasattr(user, "_cached_has_perm"):
            ret = user._cached_has_perm.get(perm, {}).get(obj)
            if ret is not None:
                return ret
        else:
            user._cached_has_perm = {}

        ret = self._has_perm(user, perm, obj)
        user._cached_has_perm.setdefault(perm, {})[obj] = ret
        return ret

    def _has_perm(self, user, perm, obj=None):
        """
        Returns True if given user has particular permission for the object.
        If no object is given, False is returned.
        """
        if not is_object_supported(obj):
            return False

        app_label, _ = perm.split(".", maxsplit=1)
        if app_label != obj._meta.app_label:
            raise ValueError("Passed perm has wrong app label: '%s'" % app_label)

        # Global permissions test. The django backend doesn't handle well
        # has_perm call when obj is not None so we have to do the check here
        # as well (https://github.com/django/django/blob/master/django/contrib/auth/backends.py#L104)
        if perm in super().get_all_permissions(user, None):
            return True

        auth = PermissionAuth(user)
        return auth.has_perm(perm, obj)

    def get_all_permissions(self, user, obj=None):
        """
        Returns a set of permissions that the given user has for object.
        """
        if not obj:
            return super().get_all_permissions(user, None)
        if not is_object_supported(obj):
            return set()

        auth = PermissionAuth(user)
        return auth.get_perms(obj)
