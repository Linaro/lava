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
from django.contrib.auth.models import Permission
from django.db import models
from django.db.models import Q, CharField
from django.db.models.functions import Cast

from lava_common.exceptions import ObjectNotPersisted, PermissionNameError
from lava_scheduler_app.auth import PermissionAuth

from django_restricted_resource.managers import RestrictedResourceQuerySet


class GroupObjectPermissionManager(models.Manager):
    def assign_perm(self, perm, group, obj):
        """
        Assigns permission for an instance and a group.
        """
        if getattr(obj, "pk", None) is None:
            raise ObjectNotPersisted("Object needs to be persisted first")
        ctype = ContentType.objects.get_for_model(obj)
        try:
            permission = Permission.objects.get(content_type=ctype, codename=perm)
        except Permission.DoesNotExist:
            raise PermissionNameError("Please use existing permission codename")

        kwargs = {
            "permission": permission,
            "group": group,
            "content_type": ctype,
            "object_id": obj.pk,
        }
        obj_perm, _ = self.get_or_create(**kwargs)
        return obj_perm

    def bulk_assign_perm(self, perm, group, queryset):
        """
        Bulk assigns permissions for an objects in queryset.
        """

        ctype = ContentType.objects.get_for_model(queryset.model)
        try:
            permission = Permission.objects.get(content_type=ctype, codename=perm)
        except Permission.DoesNotExist:
            raise PermissionNameError("Please use existing permission codename")

        assigned_perms = []
        for instance in queryset:
            perm, _ = self.get_or_create(
                permission=permission,
                group=group,
                content_type=ctype,
                object_id=instance.pk,
            )
            assigned_perms.append(perm)

        return assigned_perms

    def assign_perm_to_many(self, perm, groups, obj):
        """
        Bulk assigns given permission for the object to a set of groups.
        """
        ctype = ContentType.objects.get_for_model(obj)
        try:
            permission = Permission.objects.get(content_type=ctype, codename=perm)
        except Permission.DoesNotExist:
            raise PermissionNameError("Please use existing permission codename")

        kwargs = {"permission": permission}
        kwargs["content_type"] = ctype
        kwargs["object_id"] = obj.pk

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

        filters = Q(**{"group": group})

        ctype = ContentType.objects.get_for_model(obj)
        filters &= Q(permission__codename=perm, permission__content_type=ctype)

        filters &= Q(content_type=ctype, object_id=obj.pk)
        return self.filter(filters).delete()


class RestrictedObjectQuerySet(models.QuerySet):
    class Meta:
        abstract = True

    def restricted_by_perm(self, perm):
        from lava_scheduler_app.models import GroupObjectPermission

        # Need to transform pk to 'str' because TestJob pk is 'int' and
        # Device and DeviceType pk is 'str'.
        pks = self.annotate(pk_str=Cast("pk", CharField(max_length=255))).values_list(
            "pk_str", flat=True
        )
        filters = {
            "content_type": ContentType.objects.get_for_model(self.model),
            "object_id__in": pks,
            "permission__codename": perm,
        }
        restricted_pks = GroupObjectPermission.objects.filter(**filters).values_list(
            "object_id", flat=True
        )
        return restricted_pks

    def accessible_by_user(self, user, perm):
        raise NotImplementedError("Should implement this method")

    def visible_by_user(self, user):
        return self.accessible_by_user(user, self.model.VIEW_PERMISSION)


class RestrictedDeviceTypeQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        auth = PermissionAuth(user)

        # Always false Q object which does not produce a query.
        filters = Q(pk__in=[])
        # If the requested permission is view or the requested permission is
        # submit and user is authenticated, add unrestricted device types
        # to the filter result.
        if (perm == self.model.VIEW_PERMISSION) or (
            perm == self.model.SUBMIT_PERMISSION and user.is_authenticated
        ):
            filters = ~Q(pk__in=self.restricted_by_perm(perm))
        if user.is_authenticated:
            filters |= Q(pk__in=auth.filter_queryset_by_perms([perm], self))

        return self.filter(filters)


class RestrictedDeviceQuerySet(RestrictedObjectQuerySet):
    def accessible_by_user(self, user, perm):
        from lava_scheduler_app.models import DeviceType, Device

        auth = PermissionAuth(user)
        accessible_device_types = DeviceType.objects.filter(
            pk__in=self.values_list("device_type__pk")
        ).accessible_by_user(user, Device.DEVICE_TYPE_PERMISSION_MAP[perm])

        # For non-authenticated users, accessible device types will always be
        # empty for non-view permissions, so this will also return no results.
        # Similar for submit permissions.
        filters = ~Q(pk__in=self.restricted_by_perm(perm)) & Q(
            device_type__in=accessible_device_types
        )

        # If the user is authenticated add the permission filter too.
        if user.is_authenticated:
            filters |= Q(pk__in=auth.filter_queryset_by_perms([perm], self))

        return self.filter(filters)


class RestrictedTestJobQuerySet(RestrictedResourceQuerySet):
    def visible_by_user(self, user):

        from lava_scheduler_app.models import TestJob

        conditions = Q()
        # Pipeline jobs.
        if not user or user.is_anonymous:
            conditions = Q(is_public=True)
        elif (
            not user.is_superuser
            and not user.has_perm("lava_scheduler_app.cancel_resubmit_testjob")
            and not user.has_perm("lava_scheduler_app.change_device")
        ):
            # continue adding conditions only if user is not superuser and
            # does not have admin permission for jobs or devices.
            conditions = (
                Q(is_public=True)
                | Q(submitter=user)
                | (~Q(actual_device=None) & Q(actual_device__user=user))
                | Q(visibility=TestJob.VISIBLE_PUBLIC)
                | Q(visibility=TestJob.VISIBLE_PERSONAL, submitter=user)
                |
                # NOTE: this supposedly does OR and we need user to be in
                # all the visibility groups if we allow multiple groups in
                # field viewing groups.
                Q(
                    visibility=TestJob.VISIBLE_GROUP,
                    viewing_groups__in=user.groups.all(),
                )
            )

        return self.filter(conditions)


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
