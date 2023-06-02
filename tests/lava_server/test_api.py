# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import xmlrpc.client

import ldap
import pytest
from django.contrib.auth.models import Group, User

from lava_common.decorators import nottest
from lava_scheduler_app.models import Device, DeviceType, Worker
from tests.lava_scheduler_app.test_api import TestTransport


class TestLavaServerApi:
    @nottest
    def ensure_user(self, username, email, password, is_superuser=False):
        if User.objects.filter(username=username):
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username, email, password, is_superuser=is_superuser
            )
            user.save()
        return user

    @nottest
    def server_proxy(self, user=None, password=None):
        return xmlrpc.client.ServerProxy(
            "http://localhost/RPC2/",
            transport=TestTransport(user=user, password=password),
            allow_none=True,
        )

    @pytest.fixture(autouse=True)
    def setUp(self, db):
        # create group
        self.group = Group.objects.create(name="group1")

        # create users
        self.user1 = User.objects.create(username="user1")
        self.user2 = User.objects.create(username="user2")
        self.user1.groups.add(self.group)

        # Create workers
        self.worker1 = Worker.objects.create(
            hostname="worker1", state=Worker.STATE_ONLINE, health=Worker.HEALTH_ACTIVE
        )

        # create devicetype
        self.device_type1 = DeviceType.objects.create(name="device_type1")

        # create device
        self.device1 = Device.objects.create(
            hostname="public01", device_type=self.device_type1, worker_host=self.worker1
        )

    def test_assign_perm_devicetype_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        try:
            server.system.assign_perm_device_type(
                "lava_scheduler_app.view_devicetype",
                self.device_type1.name,
                self.group.name,
            )
        except xmlrpc.client.Fault as f:
            assert f.faultCode == 403  # nosec
        else:
            print("fault not raised")
            assert False  # nosec

    def test_assign_perm_devicetype(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        assert (  # nosec
            self.user1.has_perm("lava_scheduler_app.view_devicetype", self.device_type1)
            == False
        )
        assert (  # nosec
            self.user2.has_perm("lava_scheduler_app.view_devicetype", self.device_type1)
            == False
        )
        server.system.assign_perm_device_type(
            "lava_scheduler_app.view_devicetype",
            self.device_type1.name,
            self.group.name,
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        assert (  # nosec
            self.user1.has_perm("lava_scheduler_app.view_devicetype", self.device_type1)
            == True
        )
        assert (  # nosec
            self.user2.has_perm("lava_scheduler_app.view_devicetype", self.device_type1)
            == False
        )

    def test_revoke_perm_devicetype_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        try:
            server.system.revoke_perm_device_type(
                "lava_scheduler_app.view_devicetype",
                self.device_type1.name,
                self.group.name,
            )
        except xmlrpc.client.Fault as f:
            assert f.faultCode == 403  # nosec
        else:
            print("fault not raised")
            assert False  # nosec

    def test_revoke_perm_devicetype(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        server.system.assign_perm_device_type(
            "lava_scheduler_app.view_devicetype",
            self.device_type1.name,
            self.group.name,
        )
        assert (  # nosec
            self.user1.has_perm("lava_scheduler_app.view_devicetype", self.device_type1)
            == True
        )
        assert (  # nosec
            self.user2.has_perm("lava_scheduler_app.view_devicetype", self.device_type1)
            == False
        )
        server.system.revoke_perm_device_type(
            "lava_scheduler_app.view_devicetype",
            self.device_type1.name,
            self.group.name,
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        assert (  # nosec
            self.user1.has_perm("lava_scheduler_app.view_devicetype", self.device_type1)
            == False
        )
        assert (  # nosec
            self.user2.has_perm("lava_scheduler_app.view_devicetype", self.device_type1)
            == False
        )

    def test_assign_perm_device_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        try:
            server.system.assign_perm_device(
                "lava_scheduler_app.view_device", self.device1.hostname, self.group.name
            )
        except xmlrpc.client.Fault as f:
            assert f.faultCode == 403  # nosec
        else:
            print("fault not raised")
            assert False  # nosec

    def test_assign_perm_device(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        assert (  # nosec
            self.user1.has_perm("lava_scheduler_app.view_device", self.device1) == False
        )
        assert (  # nosec
            self.user2.has_perm("lava_scheduler_app.view_device", self.device1) == False
        )
        server.system.assign_perm_device(
            "lava_scheduler_app.view_device", self.device1.hostname, self.group.name
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        assert (  # nosec
            self.user1.has_perm("lava_scheduler_app.view_device", self.device1) == True
        )
        assert (  # nosec
            self.user2.has_perm("lava_scheduler_app.view_device", self.device1) == False
        )

    def test_revoke_perm_device_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        try:
            server.system.revoke_perm_device(
                "lava_scheduler_app.view_device", self.device1.hostname, self.group.name
            )
        except xmlrpc.client.Fault as f:
            assert f.faultCode == 403  # nosec
        else:
            print("fault not raised")
            assert False  # nosec

    def test_revoke_perm_device(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        server.system.assign_perm_device(
            "lava_scheduler_app.view_device", self.device1.hostname, self.group.name
        )
        assert (  # nosec
            self.user1.has_perm("lava_scheduler_app.view_device", self.device1) == True
        )
        assert (  # nosec
            self.user2.has_perm("lava_scheduler_app.view_device", self.device1) == False
        )
        server.system.revoke_perm_device(
            "lava_scheduler_app.view_device", self.device1.hostname, self.group.name
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        assert (  # nosec
            self.user1.has_perm("lava_scheduler_app.view_device", self.device1) == False
        )
        assert (  # nosec
            self.user2.has_perm("lava_scheduler_app.view_device", self.device1) == False
        )

    def test_auth_groups_add_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.add("group11")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString == "User 'test' is missing permission auth.add_group."
        )

    def test_auth_groups_add(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        server.auth.groups.add("group11")
        assert Group.objects.filter(name="group11").exists()

    def test_auth_groups_add_already_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.add("group1")
        assert exc.value.faultCode == 400
        assert exc.value.faultString == "Bad request: group already exists?"

    def test_auth_groups_delete_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.delete("group1")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.change_group."
        )

    def test_auth_groups_delete(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        server.auth.groups.delete("group1")
        assert Group.objects.filter(name="group1").first() is None

    def test_auth_groups_delete_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.delete("group11")
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Bad request: group does not exists"

    def test_auth_groups_list_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.list()
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.view_group."
        )

    def test_auth_groups_list(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        groups = server.auth.groups.list()
        assert "group1" in groups

    def test_auth_groups_show_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.show("group1")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.view_group."
        )

    def test_auth_groups_show(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        group_info = server.auth.groups.show("group1")
        assert isinstance(group_info["id"], int)
        assert group_info["name"] == "group1"
        assert group_info["permissions"] == []
        assert group_info["users"] == ["user1"]

    def test_auth_groups_show_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.show("group11")
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Group 'group11' was not found."

    def test_auth_groups_perms_add_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.add(
                "group1", "lava_scheduler_app", "devicetype", "change_devicetype"
            )
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.change_group."
        )

    def test_auth_groups_perms_add(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        group = Group.objects.get(name="group1")
        group.permissions.filter(codename="change_devicetype") is None
        server.auth.groups.perms.add(
            "group1", "lava_scheduler_app", "devicetype", "change_devicetype"
        )
        assert group.permissions.filter(codename="change_devicetype")

    def test_auth_groups_perms_add_group_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.add(
                "group_not_exist",
                "lava_scheduler_app",
                "devicetype",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Group 'group_not_exist' was not found."

    def test_auth_groups_perms_add_app_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.add(
                "group1",
                "app_not_exist",
                "devicetype",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Invalid app.model 'app_not_exist.devicetype'"

    def test_auth_groups_perms_add_model_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.add(
                "group1",
                "lava_scheduler_app",
                "model_not_exist",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert (
            exc.value.faultString
            == "Invalid app.model 'lava_scheduler_app.model_not_exist'"
        )

    def test_auth_groups_perms_add_perm_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.add(
                "group1",
                "lava_scheduler_app",
                "devicetype",
                "perm_not_exist",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Invalid permission 'perm_not_exist'"

    def test_auth_groups_perms_list_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.list("group1")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.view_group."
        )

    def test_auth_groups_perms_list(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        perms = server.auth.groups.perms.list("group1")
        assert perms == []

    def test_auth_groups_perms_list_group_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.list("group11")
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Group 'group11' was not found."

    def test_auth_groups_perms_delete_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.delete(
                "group1", "lava_scheduler_app", "devicetype", "change_devicetype"
            )
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.change_group."
        )

    def test_auth_groups_perms_delete(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        server.auth.groups.perms.add(
            "group1", "lava_scheduler_app", "devicetype", "change_devicetype"
        )
        group = Group.objects.get(name="group1")
        assert group.permissions.filter(codename="change_devicetype")
        server.auth.groups.perms.delete(
            "group1", "lava_scheduler_app", "devicetype", "change_devicetype"
        )
        assert not group.permissions.filter(codename="change_devicetype")

    def test_auth_groups_perms_delete_group_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.delete(
                "group_not_exist",
                "lava_scheduler_app",
                "devicetype",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Group 'group_not_exist' was not found."

    def test_auth_groups_perms_delete_app_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.delete(
                "group1",
                "app_not_exist",
                "devicetype",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Invalid app.model 'app_not_exist.devicetype'"

    def test_auth_groups_perms_delete_model_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.delete(
                "group1",
                "lava_scheduler_app",
                "model_not_exist",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert (
            exc.value.faultString
            == "Invalid app.model 'lava_scheduler_app.model_not_exist'"
        )

    def test_auth_groups_perms_delete_perm_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.groups.perms.delete(
                "group1",
                "lava_scheduler_app",
                "devicetype",
                "perm_not_exist",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Invalid permission 'perm_not_exist'"

    def test_auth_users_add_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.add("user11")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString == "User 'test' is missing permission auth.add_user."
        )

    def test_auth_users_add(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        server.auth.users.add("user11", "first", "last", "first.last@mail")
        assert User.objects.filter(username="user11").exists()
        user = User.objects.get(username="user11")
        assert user.first_name == "first"
        assert user.last_name == "last"
        assert user.email == "first.last@mail"
        assert user.is_active

        server.auth.users.add("user12", None, None, None, False, False, False)
        user = User.objects.get(username="user12")
        assert not user.is_active
        assert not user.is_staff
        assert not user.is_superuser

        server.auth.users.add("user13", None, None, None, True, True, False)
        user = User.objects.get(username="user13")
        assert user.is_active
        assert user.is_staff
        assert not user.is_superuser

        server.auth.users.add("user14", None, None, None, True, True, True)
        user = User.objects.get(username="user14")
        assert user.is_active
        assert user.is_staff
        assert user.is_superuser

    def test_auth_users_add_ldap_false(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        server.auth.users.add(
            "first.last", None, None, None, False, False, False, False
        )
        user = User.objects.get(username="first.last")
        assert user.first_name == ""
        assert user.last_name == ""
        assert user.email == ""

    def test_auth_users_add_ldap_true(self, mocker):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        mocker.patch(
            "lava_server.api.users.get_ldap_user_properties",
            return_value={
                "uid": "first.last",
                "mail": "first.last@linaro.org",
                "sn": "Last",
                "given_name": "First",
            },
        )

        server.auth.users.add("first.last", None, None, None, False, False, False, True)
        user = User.objects.get(username="first.last")
        assert user.first_name == "First"
        assert user.last_name == "Last"
        assert user.email == "first.last@linaro.org"

    def test_auth_users_add_ldap_user_not_found(self, mocker):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        mocker.patch(
            "lava_server.api.users.get_ldap_user_properties",
            side_effect=ldap.NO_SUCH_OBJECT,
        )
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.add(
                "first.last", None, None, None, False, False, False, True
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "User 'first.last' was not found in LDAP."

    def test_auth_users_add_ldap_unavailable(self, mocker):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        mocker.patch(
            "lava_server.api.users.get_ldap_user_properties",
            side_effect=ldap.UNAVAILABLE,
        )
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.add(
                "first.last", None, None, None, False, False, False, True
            )
        assert exc.value.faultCode == 400
        assert (
            exc.value.faultString
            == "Bad request: authentication via LDAP not configured."
        )

    def test_auth_users_delete_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.delete("user1")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.change_user."
        )

    def test_auth_users_delete(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        server.auth.users.delete("user1")
        assert Group.objects.filter(name="user1").first() is None

    def test_auth_users_delete_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.delete("user11")
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Bad request: user does not exists"

    def test_auth_users_list_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.list()
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString == "User 'test' is missing permission auth.view_user."
        )

    def test_auth_users_list(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")
        users = server.auth.users.list()
        assert len(users) >= 2

    def test_auth_users_show_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.show("user1")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString == "User 'test' is missing permission auth.view_user."
        )

    def test_auth_users_show(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        user_info = server.auth.users.show("user1")
        assert isinstance(user_info["id"], int)
        assert user_info["username"] == "user1"

    def test_auth_users_show_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.show("user11")
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "User 'user11' was not found."

    def test_auth_users_update_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.update()
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.change_user."
        )

    def test_auth_users_update(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        assert User.objects.get(username="user1").first_name == ""
        server.auth.users.update("user1", "first")
        assert User.objects.get(username="user1").first_name == "first"

        assert User.objects.get(username="user1").last_name == ""
        server.auth.users.update("user1", None, "last")
        assert User.objects.get(username="user1").last_name == "last"

        assert User.objects.get(username="user1").email == ""
        server.auth.users.update("user1", None, None, "user1@email.net")
        assert User.objects.get(username="user1").email == "user1@email.net"

        assert User.objects.get(username="user1").is_active
        server.auth.users.update("user1", None, None, None, False)
        assert not User.objects.get(username="user1").is_active

        assert not User.objects.get(username="user1").is_staff
        server.auth.users.update("user1", None, None, None, None, True)
        assert User.objects.get(username="user1").is_staff

        assert not User.objects.get(username="user1").is_superuser
        server.auth.users.update("user1", None, None, None, None, None, True)
        assert User.objects.get(username="user1").is_superuser

    def test_auth_users_groups_add_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.groups.add("user2", "group1")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.change_user."
        )

    def test_auth_users_groups_add(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        user = User.objects.get(username="user2")
        assert "group1" not in [g.name for g in user.groups.all()]
        server.auth.users.groups.add("user2", "group1")
        assert "group1" in [g.name for g in user.groups.all()]

    def test_auth_users_groups_add_user_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.groups.add("user11", "group1")
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "User 'user11' was not found."

    def test_auth_users_groups_list_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.groups.list("user1")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString == "User 'test' is missing permission auth.view_user."
        )

    def test_auth_users_groups_list(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        groups = server.auth.users.groups.list("user1")
        assert "group1" in groups

    def test_auth_users_groups_delete_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.groups.delete("user1", "group1")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.change_user."
        )

    def test_auth_users_groups_delete(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        user = User.objects.get(username="user1")
        assert "group1" in [g.name for g in user.groups.all()]
        server.auth.users.groups.delete("user1", "group1")
        assert "group1" not in [g.name for g in user.groups.all()]

    def test_auth_users_groups_delete_user_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.groups.delete("user11", "group1")
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "User 'user11' was not found."

    def test_auth_users_groups_delete_group_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.groups.delete("user1", "group11")
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Group 'group11' was not found."

    def test_auth_users_perms_add_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.add(
                "user1", "lava_scheduler_app", "devicetype", "change_devicetype"
            )
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.change_user."
        )

    def test_auth_users_perms_add(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        user = User.objects.get(username="user1")
        user.user_permissions.filter(codename="change_devicetype") is None
        server.auth.users.perms.add(
            "user1", "lava_scheduler_app", "devicetype", "change_devicetype"
        )
        assert user.user_permissions.filter(codename="change_devicetype")

    def test_auth_users_perms_add_user_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.add(
                "user_not_exist",
                "lava_scheduler_app",
                "devicetype",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "User 'user_not_exist' was not found."

    def test_auth_users_perms_add_app_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.add(
                "user1",
                "app_not_exist",
                "devicetype",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Invalid app.model 'app_not_exist.devicetype'"

    def test_auth_users_perms_add_model_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.add(
                "user1",
                "lava_scheduler_app",
                "model_not_exist",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert (
            exc.value.faultString
            == "Invalid app.model 'lava_scheduler_app.model_not_exist'"
        )

    def test_auth_users_perms_add_perm_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.add(
                "user1",
                "lava_scheduler_app",
                "devicetype",
                "perm_not_exist",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Invalid permission 'perm_not_exist'"

    def test_auth_users_perms_list_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")
        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.list("user1")
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString == "User 'test' is missing permission auth.view_user."
        )

    def test_auth_users_perms_list(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        perms = server.auth.users.perms.list("user1")
        assert perms == []

    def test_auth_users_perms_list_user_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.list("user11")
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "User 'user11' was not found."

    def test_auth_users_perms_delete_unauthorized(self):
        user = self.ensure_user("test", "test@mail.net", "test")
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.delete(
                "user1", "lava_scheduler_app", "devicetype", "change_devicetype"
            )
        assert exc.value.faultCode == 403
        assert (
            exc.value.faultString
            == "User 'test' is missing permission auth.change_user."
        )

    def test_auth_users_perms_delete(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        server.auth.users.perms.add(
            "user1", "lava_scheduler_app", "devicetype", "change_devicetype"
        )
        user = User.objects.get(username="user1")
        assert user.user_permissions.filter(codename="change_devicetype")
        server.auth.users.perms.delete(
            "user1", "lava_scheduler_app", "devicetype", "change_devicetype"
        )
        assert not user.user_permissions.filter(codename="change_devicetype")

    def test_auth_users_perms_delete_user_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.delete(
                "user_not_exist",
                "lava_scheduler_app",
                "devicetype",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "User 'user_not_exist' was not found."

    def test_auth_users_perms_delete_app_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.delete(
                "user1",
                "app_not_exist",
                "devicetype",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Invalid app.model 'app_not_exist.devicetype'"

    def test_auth_users_perms_delete_model_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.delete(
                "user1",
                "lava_scheduler_app",
                "model_not_exist",
                "change_devicetype",
            )
        assert exc.value.faultCode == 404
        assert (
            exc.value.faultString
            == "Invalid app.model 'lava_scheduler_app.model_not_exist'"
        )

    def test_auth_users_perms_delete_perm_not_exist(self):
        user = self.ensure_user("test", "test@mail.net", "test", True)
        server = self.server_proxy("test", "test")

        with pytest.raises(xmlrpc.client.Fault) as exc:
            server.auth.users.perms.delete(
                "user1",
                "lava_scheduler_app",
                "devicetype",
                "perm_not_exist",
            )
        assert exc.value.faultCode == 404
        assert exc.value.faultString == "Invalid permission 'perm_not_exist'"
