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

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission, Group
from django.db import models
from django.db.models import Q

from lava_common.exceptions import ObjectNotPersisted, PermissionNameError


class GroupObjectPermissionManager(models.Manager):
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


class RestrictedObjectQuerySet(models.QuerySet):
    class Meta:
        abstract = True

    def accessible_by_user(self, user, perm):
        raise NotImplementedError("Should implement this method")

    def visible_by_user(self, user):
        return self.accessible_by_user(user, self.model.VIEW_PERMISSION)

    def restricted_by_perm(self, perm):
        """Add annotation used to determine if an object has any permissions"""
        return self.annotate(
            existing_permissions=models.Sum(
                models.Case(
                    models.When(
                        permissions__permission__codename=perm.split(".", 1)[-1], then=1
                    ),
                    default=0,
                    output_field=models.IntegerField(),
                )
            )
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
            perm_count=models.Sum(
                models.Case(
                    models.When(
                        permissions__permission__codename__in=perms,
                        permissions__group__user=user,
                        then=1,
                    ),
                    default=0,
                    output_field=models.IntegerField(),
                )
            )
        )


class RestrictedWorkerQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        if user.is_superuser or perm in user.get_all_permissions():
            return self
        else:
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
        if user.is_superuser or perm in user.get_all_permissions():
            return self
        else:
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
        from lava_scheduler_app.models import DeviceType, Device

        if user.is_superuser or perm in user.get_all_permissions():
            return self
        else:
            accessible_device_types = DeviceType.objects.accessible_by_user(
                user, Device.DEVICE_TYPE_PERMISSION_MAP[perm]
            )

            # For non-authenticated users, accessible device types will always
            # be empty for non-view permissions, so this will also return no
            # results. Similar for submit permissions.
            filters = Q(existing_permissions=0) & Q(
                device_type__in=accessible_device_types
            )
            # If the user is authenticated add the main permission filter.
            if user.is_authenticated:
                self = self.filter_by_perm(perm, user)
                filters |= ~Q(perm_count=0)

            return self.restricted_by_perm(perm).filter(filters)


class RestrictedTestJobQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        from lava_scheduler_app.models import Device, DeviceType, TestJob

        if user.is_superuser or perm in user.get_all_permissions():
            return self
        else:
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
            non_vg_ids = TestJob.objects.filter(viewing_groups=None)
            filters |= (
                Q(is_public=True)
                & Q(id__in=non_vg_ids)
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
            if perm == self.model.VIEW_PERMISSION:
                # Needed to determine if viewing_groups is subset of all users
                # groups, so remove all jobs where any viewing group is in groups
                # this user is not part of.
                nonuser_groups = Group.objects.exclude(
                    pk__in=[g.id for g in user.groups.all()]
                )
                # NOTE: Only the last two conditions will be ANDed. Keep in mind if
                # another filter needs to be added in between this one and the one
                # before.
                filters |= ~Q(id__in=non_vg_ids) & ~Q(viewing_groups__in=nonuser_groups)

            return self.filter(filters)


class RestrictedTestCaseQuerySet(models.QuerySet):
    def visible_by_user(self, user):

        from lava_scheduler_app.models import TestJob

        jobs = TestJob.objects.filter(testsuite__testcase__in=self).visible_by_user(
            user
        )
        return self.filter(suite__job__in=jobs)


class RestrictedTestSuiteQuerySet(models.QuerySet):
    def visible_by_user(self, user):

        from lava_scheduler_app.models import TestJob

        jobs = TestJob.objects.filter(testsuite__in=self).visible_by_user(user)
        return self.filter(job__in=jobs)
