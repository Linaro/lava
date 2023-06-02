# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from itertools import chain

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


class PermissionAuth:
    def __init__(self, user):
        self.user = user

    def has_perm(self, perm, obj):
        """
        Checks if user has given permission for object.

        :param perm: permission as string, must contain app_label
        :param obj: Django model instance for which permission should be checked
        """
        # Handle anonymous users.
        if not self.user.is_authenticated:
            # Anonymous users can only have view permission and only when
            # the object does not have any view permission restrictions.
            if perm == obj.VIEW_PERMISSION:
                return not obj.has_any_permission_restrictions(obj.VIEW_PERMISSION)
            else:
                return False
        # Handle inactive and super users.
        if not self.user.is_active:
            return False
        if self.user.is_superuser:
            return True

        _, perm = perm.split(".", 1)
        return perm in self.get_perms(obj)

    def get_group_perms(self, obj):
        content_type = ContentType.objects.get_for_model(obj)

        perms_queryset = Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(obj)
        )
        fieldname = "group%spermission__group__user" % content_type.model

        filters = {fieldname: self.user}
        filters[
            "group%spermission__%s" % (content_type.model, content_type.model)
        ] = obj

        perms_queryset = perms_queryset.filter(**filters)
        perms = set(perms_queryset.values_list("codename", flat=True))
        # Add lower priority permissions the resulting set.
        for perm in perms.copy():
            for idx, lower_perm in enumerate(obj.PERMISSIONS_PRIORITY):
                if idx > obj.PERMISSIONS_PRIORITY.index(
                    "%s.%s" % (content_type.app_label, perm)
                ):
                    perms.add(lower_perm.split(".", 1)[-1])

        return perms

    def get_perms(self, obj):
        """
        Returns list of codenames of all permissions for given object.

        :param obj: Django model instance for which permission should be checked
        """
        if not self.user.is_active:
            return []
        content_type = ContentType.objects.get_for_model(obj)
        if self.user.is_superuser:
            perms = set(
                chain(
                    *Permission.objects.filter(content_type=content_type).values_list(
                        "codename"
                    )
                )
            )
        else:
            perms = set(self.get_group_perms(obj))
        return perms
