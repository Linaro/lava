# Copyright (C) 2015-2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Manager, OuterRef, Q, QuerySet, Subquery

from lava_common.exceptions import ObjectNotPersisted, PermissionNameError

if TYPE_CHECKING:
    from django.contrib.auth.models import User


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

    def filter_by_perm(
        self,
        perm: str,
        user: User,
        include_objects_without_permissions: bool | Q = False,
    ):
        """Filter queryset by specific permission.

        Returns queryset object based on user authorization with permission
        perm over objects from queryset.

        :param str perm: permission, must contain app_label
        :param User user: User to filter objects against
        :param bool | Q include_objects_without_permissions: Include objects
            without permissions set. Takes either a boolean or a Q object that
            objects without permissions will also be filtered against.
        """

        filters = Q(pk__in=[])

        if include_objects_without_permissions:
            objects_without_permissions = ~Q(
                permissions__permission__codename=perm.split(".", 1)[-1]
            )

            if isinstance(include_objects_without_permissions, Q):
                objects_without_permissions &= include_objects_without_permissions

            filters |= objects_without_permissions

        if user.is_authenticated:
            perms_priorized = [
                x.split(".", 1)[-1]
                for i, x in enumerate(self.model.PERMISSIONS_PRIORITY)
                if self.model.PERMISSIONS_PRIORITY.index(perm) >= i
            ]
            filters |= Q(
                pk__in=self.filter(
                    Q(
                        permissions__permission__codename__in=perms_priorized,
                        permissions__group__user=user,
                    )
                )
            )

        return self.filter(filters)


class RestrictedWorkerQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        if user.has_perm(perm):
            # Superusers have all permissions
            return self

        return self.filter_by_perm(perm, user)

    def visible_by_user(self, user):
        raise NotImplementedError("Not supported for Worker model")


class RestrictedDeviceTypeQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        if user.has_perm(perm):
            # Superusers have all permissions
            return self

        return self.filter_by_perm(
            perm,
            user,
            include_objects_without_permissions=(
                (perm == self.model.VIEW_PERMISSION)
                or (perm == self.model.SUBMIT_PERMISSION and user.is_authenticated)
            ),
        )


class RestrictedDeviceQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        if user.has_perm(perm):
            # Superusers have all permissions
            return self

        from lava_scheduler_app.models import Device, DeviceType

        accessible_device_types = DeviceType.objects.accessible_by_user(
            user,
            Device.DEVICE_TYPE_PERMISSION_MAP[perm],
        )

        return self.filter_by_perm(
            perm, user, Q(device_type__in=accessible_device_types)
        )


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
        vg_ids = Subquery(
            Group.objects.filter(viewing_groups=OuterRef("pk")).values("viewing_groups")
        )
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
            nonuser_groups = Group.objects.difference(user.groups.all()).values("pk")
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
