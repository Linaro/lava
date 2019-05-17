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


from itertools import chain

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


class PermissionAuth:
    def __init__(self, user):
        self.user = user
        self._cache = {}

    def has_perm(self, perm, obj):
        """
        Checks if user has given permission for object.

        Checks for unsupported models will return False.

        :param perm: permission as string, must contain app_label
        :param obj: Django model instance for which permission should be checked
        """
        _, perm = perm.split(".", 1)

        # Handle anonymous users.
        if not self.user.is_authenticated:
            if perm == obj.VIEW_PERMISSION:
                return not obj.has_any_permission_restrictions(obj.VIEW_PERMISSION)
            else:
                return False
        # Handle inactive and super users.
        if not self.user.is_active:
            return False
        if self.user.is_superuser:
            return True

        return perm in self.get_perms(obj)

    def get_group_perms(self, obj):
        from lava_scheduler_app.models import GroupObjectPermission

        content_type = ContentType.objects.get_for_model(obj)
        perms_queryset = Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(obj)
        )

        rel_name = GroupObjectPermission.permission.field.related_query_name()
        fieldname = "%s__group__%s" % (
            rel_name,
            get_user_model().groups.field.related_query_name(),
        )
        group_filters = {fieldname: self.user}
        group_filters["%s__content_type" % rel_name] = content_type
        group_filters["%s__object_id" % rel_name] = obj.pk

        group_perms_queryset = perms_queryset.filter(**group_filters)
        group_perms = set(group_perms_queryset.values_list("codename", flat=True))
        # Add lower priority permissions the resulting set.
        for perm in group_perms.copy():
            for idx, lower_perm in enumerate(obj.PERMISSIONS_PRIORITY):
                if idx > obj.PERMISSIONS_PRIORITY.index(perm):
                    group_perms.add(lower_perm)

        return group_perms

    def get_perms(self, obj):
        """
        Returns list of codenames of all permissions for given object.

        :param obj: Django model instance for which permission should be checked
        """
        if not self.user.is_active:
            return []
        content_type = ContentType.objects.get_for_model(obj)
        key = self.get_local_cache_key(obj)
        if key not in self._cache:
            if self.user.is_superuser:
                perms = set(
                    chain(
                        *Permission.objects.filter(
                            content_type=content_type
                        ).values_list("codename")
                    )
                )
            else:
                perms = set(self.get_group_perms(obj))
            self._cache[key] = perms
        return self._cache[key]

    def get_local_cache_key(self, obj):
        """
        Returns cache key for _cache dict.
        """
        content_type = ContentType.objects.get_for_model(obj)
        return (content_type.id, str(obj.pk))

    def prefetch_perms(self, queryset):
        """
        Prefetches the permissions for objects and puts them in the cache.

        :param queryset: Django model queryset
        """
        from lava_scheduler_app.models import GroupObjectPermission

        if not queryset or not self.user.is_active:
            return []

        User = get_user_model()

        # Get content_type and primary keys from the queryset.
        pks = [str(pk) for pk in queryset.values_list("pk", flat=True)]
        content_type = ContentType.objects.get_for_model(queryset.model)

        if self.user.is_superuser:
            perms = set(
                chain(
                    *Permission.objects.filter(content_type=content_type).values_list(
                        "codename"
                    )
                )
            )
            for pk in pks:
                key = (content_type.id, str(pk))
                self._cache[key] = perms
            return True

        filters = {
            "group__%s" % User.groups.field.related_query_name(): self.user,
            "content_type": content_type,
            "object_id__in": pks,
        }
        # Init cache.
        for obj in queryset:
            key = self.get_local_cache_key(obj)
            self._cache[key] = set()

        # First, add relevant global permissions.
        for perm in self.user.get_all_permissions():
            if perm.rsplit("_", 1)[1] == content_type:
                for pk in pks:
                    key = (content_type.id, str(pk))
                    self._cache[key].add(perm.split(".", 1)[1])

        perms = GroupObjectPermission.objects.filter(**filters).select_related(
            "permission"
        )
        # Add permissions to cache for each object.
        for perm in perms:
            key = (content_type.id, perm.object_id)
            self._cache[key].add(perm.permission.codename)
            # Add lower priority permissions to cache.
            for idx, lower_perm in enumerate(
                content_type.model_class().PERMISSIONS_PRIORITY
            ):
                if idx > content_type.model_class().PERMISSIONS_PRIORITY.index(
                    perm.permission.codename
                ):
                    self._cache[key].add(lower_perm)

        return True

    def filter_queryset_by_perms(self, perms, queryset, match_all=False):
        """Filters queryset by specific permission.

        Returns a list of pk's which user is authorized to access with
        permissions perms.
        Permission must match the content_type of the specified queryset.

        :param perms: permissions as a list, must contain app_label
        :param queryset: Django queryset to be filtered by perms
        :param match_all: If True, then user needs to have all requested
                          permissions for each object. Otherwise, at least one.
        """

        content_type = ContentType.objects.get_for_model(queryset.model)
        perm_codenames = set()

        for perm in perms:
            app_label, codename = perm.split(".", 1)
            if app_label != content_type.app_label:
                raise ValueError(
                    "perm should belong to the same app as queryset content type provided (%s, %s)"
                    % (app_label, content_type.app_label)
                )
            # Raise if the permission does not belong to the provided
            # content_type or is generally non existing.
            try:
                Permission.objects.get(content_type=content_type, codename=codename)
            except Permission.DoesNotExist:
                raise ValueError(
                    "Only existing permissions and permissions related to the provided content_type %s are allowed."
                    % content_type
                )

            perm_codenames.add(codename)

        self.prefetch_perms(queryset)
        if not match_all:
            # If intersection between user permissions for the object and
            # requested permissions exist, then user is authorized.
            authorized_pks = [
                key[1] for key in self._cache if self._cache[key] & perm_codenames
            ]
        else:
            # Unless we need to match all requested permissions.
            authorized_pks = [
                key[1]
                for key in self._cache
                if perm_codenames.issubset(self._cache[key])
            ]

        return authorized_pks
