import xmlrpc

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from lava_scheduler_app.api import check_perm
from lava_scheduler_app.utils import get_ldap_user_properties
from linaro_django_xmlrpc.models import ExposedV2API


class UsersAPI(ExposedV2API):
    @check_perm("auth.add_user")
    def add(
        self,
        username,
        first_name=None,
        last_name=None,
        email=None,
        is_active=True,
        is_staff=False,
        is_superuser=False,
        ldap=False,
    ):
        try:
            args = {
                "username": username,
                "is_active": is_active,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
            }
            if first_name is not None:
                args["first_name"] = first_name
            if last_name is not None:
                args["last_name"] = last_name
            if email is not None:
                args["email"] = email
            if ldap:
                import ldap

                ldap_user = get_ldap_user_properties(username)
                args["first_name"] = ldap_user.get("given_name", "")
                args["last_name"] = ldap_user.get("sn", "")
                args["email"] = ldap_user.get("mail", "")
            user = User.objects.create(**args)
        except (IntegrityError, ValidationError) as exc:
            raise xmlrpc.client.Fault(400, "Bad request: user already exists?")
        except ldap.NO_SUCH_OBJECT:
            raise xmlrpc.client.Fault(
                404, "User '%s' was not found in LDAP." % username
            )
        except ldap.UNAVAILABLE:
            raise xmlrpc.client.Fault(
                400, "Bad request: authentication via LDAP not configured."
            )

    @check_perm("auth.change_user")
    def delete(self, username):
        try:
            User.objects.get(username=username).delete()
        except User.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Bad request: user does not exists")

    @check_perm("auth.view_user")
    def list(self):
        return [
            {
                "username": u.username,
                "last_name": u.last_name,
                "first_name": u.first_name,
                "is_superuser": u.is_superuser,
                "is_staff": u.is_staff,
                "is_active": u.is_active,
            }
            for u in User.objects.all().order_by("username")
        ]

    @check_perm("auth.view_user")
    def show(self, username):
        try:
            user = User.objects.get(username=username)
            return {
                "date_joined": user.date_joined,
                "email": user.email,
                "first_name": user.first_name,
                "groups": [g.name for g in user.groups.all()],
                "permissions": [
                    f"{p.content_type.app_label}.{p.content_type.model}.{p.codename}"
                    for p in user.user_permissions.all()
                ],
                "id": user.id,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "last_login": user.last_login,
                "last_name": user.last_name,
                "username": user.username,
            }
        except User.DoesNotExist:
            raise xmlrpc.client.Fault(404, "User '%s' was not found." % username)

    @check_perm("auth.change_user")
    def update(
        self,
        username,
        first_name=None,
        last_name=None,
        email=None,
        is_active=None,
        is_staff=None,
        is_superuser=None,
    ):
        try:
            user = User.objects.get(username=username)
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            if email is not None:
                user.email = email
            if is_active is not None:
                user.is_active = is_active
            if is_staff is not None:
                user.is_staff = is_staff
            if is_superuser is not None:
                user.is_superuser = is_superuser
            user.save()
        except User.DoesNotExist:
            raise xmlrpc.client.Fault(404, "User '%s' was not found." % username)
        except (IntegrityError, ValidationError) as exc:
            raise xmlrpc.client.Fault(400, "Bad request")


class UsersGroupsAPI(ExposedV2API):
    @check_perm("auth.change_user")
    def add(self, username, group):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise xmlrpc.client.Fault(404, "User '%s' was not found." % username)

        group, _ = Group.objects.get_or_create(name=group)
        user.groups.add(group)

    @check_perm("auth.view_user")
    def list(self, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise xmlrpc.client.Fault(404, "User '%s' was not found." % username)

        return [g.name for g in user.groups.all()]

    @check_perm("auth.change_user")
    def delete(self, username, group):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise xmlrpc.client.Fault(404, "User '%s' was not found." % username)

        try:
            group = Group.objects.get(name=group)
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Group '%s' was not found." % group)

        user.groups.remove(group)


class UsersPermissionsAPI(ExposedV2API):
    @check_perm("auth.change_user")
    def add(self, username, app, model, codename):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise xmlrpc.client.Fault(404, "User '%s' was not found." % username)
        try:
            ct = ContentType.objects.get(app_label=app, model=model)
        except ContentType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Invalid app.model '%s.%s'" % (app, model))
        try:
            perm = Permission.objects.get(content_type=ct, codename=codename)
        except Permission.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Invalid permission '%s'" % (codename))
        user.user_permissions.add(perm)

    @check_perm("auth.view_user")
    def list(self, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise xmlrpc.client.Fault(404, "User '%s' was not found." % username)
        return [
            {
                "app": p.content_type.app_label,
                "model": p.content_type.model,
                "codename": p.codename,
            }
            for p in user.user_permissions.all()
        ]

    @check_perm("auth.change_user")
    def delete(self, username, app, model, codename):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise xmlrpc.client.Fault(404, "User '%s' was not found." % username)
        try:
            ct = ContentType.objects.get(app_label=app, model=model)
        except ContentType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Invalid app.model '%s.%s'" % (app, model))
        try:
            perm = Permission.objects.get(content_type=ct, codename=codename)
        except Permission.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Invalid permission '%s'" % (codename))
        user.user_permissions.remove(perm)
