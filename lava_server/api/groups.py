import xmlrpc

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from lava_scheduler_app.api import check_perm
from linaro_django_xmlrpc.models import ExposedV2API


class GroupsAPI(ExposedV2API):
    @check_perm("auth.add_group")
    def add(
        self,
        name,
    ):
        try:
            group = Group.objects.create(name=name)
        except (IntegrityError, ValidationError) as exc:
            raise xmlrpc.client.Fault(400, "Bad request: group already exists?")

    @check_perm("auth.change_group")
    def delete(self, name):
        try:
            Group.objects.get(name=name).delete()
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Bad request: group does not exists")

    @check_perm("auth.view_group")
    def list(self):
        return [g.name for g in Group.objects.all().order_by("name")]

    @check_perm("auth.view_group")
    def show(self, name):
        try:
            group = Group.objects.get(name=name)
            return {
                "id": group.id,
                "name": group.name,
                "permissions": [
                    f"{p.content_type.app_label}.{p.content_type.model}.{p.codename}"
                    for p in group.permissions.all()
                ],
                "users": [u.username for u in group.user_set.all()],
            }
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Group '%s' was not found." % name)


class GroupsPermissionsAPI(ExposedV2API):
    @check_perm("auth.change_group")
    def add(self, name, app, model, codename):
        try:
            group = Group.objects.get(name=name)
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Group '%s' was not found." % name)
        try:
            ct = ContentType.objects.get(app_label=app, model=model)
        except ContentType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Invalid app.model '%s.%s'" % (app, model))
        try:
            perm = Permission.objects.get(content_type=ct, codename=codename)
        except Permission.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Invalid permission '%s'" % (codename))
        group.permissions.add(perm)

    @check_perm("auth.view_group")
    def list(self, name):
        try:
            group = Group.objects.get(name=name)
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Group '%s' was not found." % name)
        return [
            {
                "app": p.content_type.app_label,
                "model": p.content_type.model,
                "codename": p.codename,
            }
            for p in group.permissions.all()
        ]

    @check_perm("auth.change_group")
    def delete(self, name, app, model, codename):
        try:
            group = Group.objects.get(name=name)
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Group '%s' was not found." % name)
        try:
            ct = ContentType.objects.get(app_label=app, model=model)
        except ContentType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Invalid app.model '%s.%s'" % (app, model))
        try:
            perm = Permission.objects.get(content_type=ct, codename=codename)
        except Permission.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Invalid permission '%s'" % (codename))
        group.permissions.remove(perm)
