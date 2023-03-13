# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Linaro Limited
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
from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Manager, Q, QuerySet

from lava_common.exceptions import ObjectNotPersisted, PermissionNameError


class GroupObjectPermissionManager(Manager):
    def assign_perm(self, perm, group, obj):
        """
        Assigns permission for an instance and a group.
        """
        if not getattr(obj, "pk", None):
            raise ObjectNotPersisted("Object needs to be persisted first")
        ctype = ContentType.objects.get_for_model(obj)

        try:
            permission = Permission.objects.get(
                content_type=ctype, codename=perm.split(".", 1)[-1]
            )
        except Permission.DoesNotExist:
            raise PermissionNameError("Please use existing permission codename")

        kwargs = {"permission": permission, "group": group, ctype.model: obj}
        obj_perm, _ = self.get_or_create(**kwargs)
        return obj_perm

    def bulk_assign_perm(self, perm, group, queryset):
        """
        Bulk assigns permissions for an objects in queryset.
        """

        ctype = ContentType.objects.get_for_model(queryset.model)
        try:
            permission = Permission.objects.get(
                content_type=ctype, codename=perm.split(".", 1)[-1]
            )
        except Permission.DoesNotExist:
            raise PermissionNameError("Please use existing permission codename")

        assigned_perms = []
        for instance in queryset:
            kwargs = {"permission": permission, "group": group, ctype.model: instance}
            perm, _ = self.get_or_create(**kwargs)
            assigned_perms.append(perm)

        return assigned_perms

    def assign_perm_to_many(self, perm, groups, obj):
        """
        Bulk assigns given permission for the object to a set of groups.
        """
        ctype = ContentType.objects.get_for_model(obj)
        try:
            permission = Permission.objects.get(
                content_type=ctype, codename=perm.split(".", 1)[-1]
            )
        except Permission.DoesNotExist:
            raise PermissionNameError("Please use existing permission codename")

        kwargs = {"permission": permission, ctype.model: obj}
        to_add = []
        for group in groups:
            kwargs["group"] = group
            to_add.append(self.model(**kwargs))

        return self.model.objects.bulk_create(to_add)

    def remove_perm(self, perm, group, obj):
        """
        Removes permission for an instance and given group.

        We use Queryset.delete method for removing the permission.
        The post_delete signals will not be fired.
        """
        if getattr(obj, "pk", None) is None:
            raise ObjectNotPersisted("Object %s needs to be persisted first" % obj)

        ctype = ContentType.objects.get_for_model(obj)
        kwargs = {
            "group": group,
            "permission__codename": perm.split(".", 1)[-1],
            "permission__content_type": ctype,
            ctype.model: obj,
        }
        return self.filter(**kwargs).delete()


class RestrictedObjectQuerySet(QuerySet):
    class Meta:
        abstract = True

    def accessible_by_user(self, user, perm):
        raise NotImplementedError("Should implement this method")

    def visible_by_user(self, user):
        return self.accessible_by_user(user, self.model.VIEW_PERMISSION)

    def restricted_by_perm(self, perm):
        """Add annotation used to determine if an object has any permissions"""
        return self.annotate(
            existing_permissions=Count(
                "permissions",
                filter=Q(permissions__permission__codename=perm.split(".", 1)[-1]),
            ),
        )

    def filter_by_perm(self, perm, user):
        """Add annotation used to filter queryset by specific permission.

        Returns queryset object based on user authorization with permission
        perm over objects from queryset with annotation which shows how many
        GroupPermission objects are related to each object.

        :param perm: permission, must contain app_label
        :param queryset: Django queryset to be filtered by perms
        """
        perms = [
            x.split(".", 1)[-1]
            for i, x in enumerate(self.model.PERMISSIONS_PRIORITY)
            if self.model.PERMISSIONS_PRIORITY.index(perm) >= i
        ]

        return self.annotate(
            perm_count=Count(
                "permissions",
                filter=Q(
                    permissions__permission__codename__in=perms,
                    permissions__group__user=user,
                ),
            ),
        )


class RestrictedWorkerQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        if user.has_perm(perm):
            # Superusers have all permissions
            return self

        # Always false Q object which does not produce a query.
        filters = Q(pk__in=[])
        # If the user is authenticated add the main permission filter.
        if user.is_authenticated:
            self = self.filter_by_perm(perm, user)
            filters |= ~Q(perm_count=0)

        return self.restricted_by_perm(perm).filter(filters)

    def visible_by_user(self, user):
        raise NotImplementedError("Not supported for Worker model")


class RestrictedDeviceTypeQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        if user.has_perm(perm):
            # Superusers have all permissions
            return self

        # Always false Q object which does not produce a query.
        filters = Q(pk__in=[])
        # If the requested permission is view or the requested permission
        # is submit and user is authenticated, add unrestricted device
        # types to the filter result.
        if (perm == self.model.VIEW_PERMISSION) or (
            perm == self.model.SUBMIT_PERMISSION and user.is_authenticated
        ):
            filters |= Q(existing_permissions=0)
        # If the user is authenticated add the main permission filter.
        if user.is_authenticated:
            self = self.filter_by_perm(perm, user)
            filters |= ~Q(perm_count=0)

        return self.restricted_by_perm(perm).filter(filters)


class RestrictedDeviceQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        if user.has_perm(perm):
            # Superusers have all permissions
            return self

        from lava_scheduler_app.models import Device, DeviceType

        accessible_device_types = DeviceType.objects.accessible_by_user(
            user, Device.DEVICE_TYPE_PERMISSION_MAP[perm]
        )

        # For non-authenticated users, accessible device types will always
        # be empty for non-view permissions, so this will also return no
        # results. Similar for submit permissions.
        filters = Q(existing_permissions=0) & Q(device_type__in=accessible_device_types)
        # If the user is authenticated add the main permission filter.
        if user.is_authenticated:
            self = self.filter_by_perm(perm, user)
            filters |= ~Q(perm_count=0)

        return self.restricted_by_perm(perm).filter(filters)


class RestrictedTestJobQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        if user.has_perm(perm):
            # Superusers have all permissions
            return self

        from lava_scheduler_app.models import Device, DeviceType, TestJob

        # Here we gather accessible devices and device types.
        accessible_devices = Device.objects.accessible_by_user(
            user, TestJob.DEVICE_PERMISSION_MAP[perm]
        )
        accessible_device_types = DeviceType.objects.accessible_by_user(
            user, TestJob.DEVICE_TYPE_PERMISSION_MAP[perm]
        )

        filters = Q(pk__in=[])  # Always empty Q object for anonymous users
        # Check for private jobs where this user is submitter.
        if user.is_authenticated:
            filters = Q(is_public=False) & Q(submitter=user)
        # Similar to device filters, we first check if jobs are
        # public and if yes, we check for accessibility of either
        # actual_device or requested_device_type (depending on whether the
        # job is scheduled or not.
        vg_ids = TestJob.objects.filter(viewing_groups__isnull=False)
        filters |= (
            Q(is_public=True)
            & ~Q(id__in=vg_ids)
            & (
                (
                    Q(actual_device__isnull=False)
                    & Q(actual_device__in=accessible_devices)
                )
                | (
                    Q(actual_device__isnull=True)
                    & Q(requested_device_type__in=accessible_device_types)
                )
            )
        )

        # Add viewing_groups filter.
        if perm == self.model.VIEW_PERMISSION and user.is_authenticated:
            # Anonymous user can never be a part of the group
            # No point in adding viewing_groups filter as
            # it will only slowdown server.

            # Needed to determine if viewing_groups is subset of all users
            # groups, so remove all jobs where any viewing group is in groups
            # this user is not part of.
            nonuser_groups = Group.objects.exclude(
                pk__in=[g.id for g in user.groups.all()]
            )
            # NOTE: Only the last two conditions will be ANDed. Keep in mind if
            # another filter needs to be added in between this one and the one
            # before.
            filters |= Q(id__in=vg_ids) & ~Q(viewing_groups__in=nonuser_groups)

        return self.filter(filters)


class RestrictedTestCaseQuerySet(QuerySet):
    def visible_by_user(self, user):
        if user.has_perm("lava_results_app.view_testcase"):
            # Superusers have all permissions
            return self

        from lava_scheduler_app.models import TestJob

        jobs = TestJob.objects.filter(testsuite__testcase__in=self).visible_by_user(
            user
        )
        return self.filter(suite__job__in=jobs)


class RestrictedTestSuiteQuerySet(QuerySet):
    def visible_by_user(self, user):
        if user.has_perm("lava_results_app.view_testsuite"):
            # Superusers have all permissions
            return self

        from lava_scheduler_app.models import TestJob

        jobs = TestJob.objects.filter(testsuite__in=self).visible_by_user(user)
        return self.filter(job__in=jobs)
