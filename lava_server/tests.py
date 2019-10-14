# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
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

import pytest
import xmlrpc.client

from django.contrib.auth.models import Group, User

from lava_common.decorators import nottest
from lava_scheduler_app.models import Device, DeviceType, Worker
from lava_scheduler_app.tests.test_api import TestTransport


class TestLavaServerApi:
    @nottest
    def ensure_user(
        self, username, email, password, is_superuser=False
    ):  # pylint: disable=no-self-use
        if User.objects.filter(username=username):
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username, email, password, is_superuser=is_superuser
            )
            user.save()
        return user

    @nottest
    def server_proxy(self, user=None, password=None):  # pylint: disable=no-self-use
        return xmlrpc.client.ServerProxy(
            "http://localhost/RPC2/",
            transport=TestTransport(user=user, password=password),
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
        assert (  # nosec
            self.user1.has_perm("lava_scheduler_app.view_device", self.device1) == False
        )
        assert (  # nosec
            self.user2.has_perm("lava_scheduler_app.view_device", self.device1) == False
        )
