# Copyright (C) 2020 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import sys
from io import StringIO

import pytest
from django.core.management import call_command

from lava_scheduler_app.models import Alias, Device, DeviceType, Group, User


@pytest.mark.django_db
def test_no_sync_to_lava(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    sync_dict = mocker.MagicMock(return_value=(None, None))
    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava", sync_dict
    )

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01 [SKIP]
  -> missing 'sync_to_lava'
"""
    )


@pytest.mark.django_db
def test_exception_template(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(None, "foo"),
    )

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01 [SKIP]
  -> invalid jinja2 template
  -> foo
"""
    )


@pytest.mark.django_db
def test_invalid_template(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "aliases": ["foo", "bar"],
            "tags": ["one", "two"],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    # Do not patch jinja2.Environment.get_template so it raises error.

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01 [SKIP]
  -> invalid jinja2 template
  -> qemu01
"""
    )


@pytest.mark.django_db
def test_existing_non_synced_device(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "aliases": ["foo", "bar"],
            "tags": ["one", "two"],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    dt = DeviceType.objects.create(name="qemu")
    Device.objects.create(hostname="qemu01", is_synced=False, device_type=dt)

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01 [SKIP]
  -> created manually
"""
    )


@pytest.mark.django_db
def test_missing_device_type(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "worker": "worker-01",
            "aliases": ["foo", "bar"],
            "tags": ["one", "two"],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01 [SKIP]
  -> 'device_type' is mandatory
"""
    )


@pytest.mark.django_db
def test_existing_alias(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "aliases": ["foo", "bar"],
            "tags": ["one", "two"],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    dt = DeviceType.objects.create(name="qemu")
    Alias.objects.create(name="foo", device_type=dt)

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> create worker: worker-01
  -> alias: foo
  -> alias: bar
  -> tag: one
  -> tag: two
"""
    )


@pytest.mark.django_db
def test_output(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "aliases": ["foo", "bar"],
            "tags": ["one", "two"],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    # Create non-related device in order to test its display value later.
    DeviceType.objects.create(name="bbb")

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> create device type: qemu
  -> create worker: worker-01
  -> alias: foo
  -> alias: bar
  -> tag: one
  -> tag: two
"""
    )

    # Test the device types display.
    assert DeviceType.objects.get(name="qemu").display
    assert not DeviceType.objects.get(name="bbb").display


@pytest.mark.django_db
def test_retire(mocker):
    dt = DeviceType.objects.create(name="qemu")
    Device.objects.create(hostname="qemu01", device_type=dt, is_synced=True)

    dt = DeviceType.objects.create(name="bbb")
    Device.objects.create(hostname="bbb01", device_type=dt, is_synced=True)
    Device.objects.create(hostname="bbb02", device_type=dt, is_synced=False)

    file_list = mocker.MagicMock(return_value=[])
    mocker.patch("lava_server.files.File.list", file_list)

    out = StringIO()
    sys.stdout = out
    call_command("sync")

    assert Device.objects.get(hostname="qemu01").health == Device.HEALTH_RETIRED
    assert not DeviceType.objects.get(name="qemu").display

    assert Device.objects.get(hostname="bbb01").health == Device.HEALTH_RETIRED
    assert Device.objects.get(hostname="bbb02").health == Device.HEALTH_MAINTENANCE
    assert DeviceType.objects.get(name="bbb").display


@pytest.mark.django_db
def test_sync_not_retire(mocker):
    dt = DeviceType.objects.create(name="qemu", display=False)
    Device.objects.create(hostname="qemu01", device_type=dt, is_synced=True)
    Device.objects.create(hostname="qemu02", device_type=dt, is_synced=True)

    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={"device_type": "qemu", "worker": "worker-01"}
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    out = StringIO()
    sys.stdout = out
    call_command("sync")

    assert Device.objects.get(hostname="qemu01").health == Device.HEALTH_MAINTENANCE
    assert Device.objects.get(hostname="qemu02").health == Device.HEALTH_RETIRED
    assert DeviceType.objects.get(name="qemu").display


@pytest.mark.django_db
def test_not_sync_not_retire(mocker):
    dt = DeviceType.objects.create(name="qemu", display=False)
    Device.objects.create(hostname="qemu01", device_type=dt, is_synced=True)
    Device.objects.create(hostname="qemu02", device_type=dt, is_synced=False)

    file_list = mocker.MagicMock(return_value=[])
    mocker.patch("lava_server.files.File.list", file_list)

    out = StringIO()
    sys.stdout = out
    call_command("sync")

    assert Device.objects.get(hostname="qemu01").health == Device.HEALTH_RETIRED
    assert Device.objects.get(hostname="qemu02").health == Device.HEALTH_MAINTENANCE
    assert not DeviceType.objects.get(name="qemu").display


@pytest.mark.django_db
def test_no_user_group(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "physical_owner": "foo",
            "physical_group": "bar",
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> create device type: qemu
  -> create worker: worker-01
  -> user 'foo' does not exist
  -> group 'bar' does not exist
"""
    )


@pytest.mark.django_db
def test_user_group(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "physical_owner": "foo",
            "physical_group": "bar",
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    User.objects.create(username="foo")
    Group.objects.create(name="bar")

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> create device type: qemu
  -> create worker: worker-01
  -> user: foo
  -> group: bar
"""
    )


@pytest.mark.django_db
def test_add_delete_permission(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    # test permission add
    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "group_device_permissions": [
                ["change_device", "foo"],
                ["change_device", "bar"],
                ["view_device", "foo"],
                ["submit_to_device", "foo"],
            ],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    Group.objects.create(name="foo")
    Group.objects.create(name="bar")

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> create device type: qemu
  -> create worker: worker-01
  -> add group permission: (change_device, foo)
  -> add group permission: (change_device, bar)
  -> add group permission: (view_device, foo)
  -> add group permission: (submit_to_device, foo)
"""
    )

    # test permission delete
    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "group_device_permissions": [
                ["change_device", "foo"],
                ["change_device", "bar"],
                ["view_device", "foo"],
            ],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> add group permission: (change_device, foo)
  -> add group permission: (change_device, bar)
  -> add group permission: (view_device, foo)
  -> delete group permission: (submit_to_device, foo)
"""
    )


@pytest.mark.django_db
def test_invalid_permission(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "group_device_permissions": [["add_testset", "foo"]],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    Group.objects.create(name="foo")

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> create device type: qemu
  -> create worker: worker-01
  -> permission 'add_testset' does not exist
"""
    )


@pytest.mark.django_db
def test_no_permission_group(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "group_device_permissions": [["change_device", "foo"]],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> create device type: qemu
  -> create worker: worker-01
  -> group 'foo' does not exist
"""
    )


@pytest.mark.django_db
def test_permission_tag_remove(mocker):
    file_list = mocker.MagicMock(return_value=["qemu01"])
    mocker.patch("lava_server.files.File.list", file_list)

    mocker.patch(
        "lava_server.management.commands.sync.Command._get_sync_to_lava",
        return_value=(mocker, None),
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={
            "device_type": "qemu",
            "worker": "worker-01",
            "group_device_permissions": [["change_device", "foo"]],
        }
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    mocker.patch("jinja2.Environment.get_template")
    mocker.patch("lava_common.yaml.load")

    Group.objects.create(name="foo")

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> create device type: qemu
  -> create worker: worker-01
  -> add group permission: (change_device, foo)
"""
    )

    parse_sync_dict = mocker.MagicMock(
        return_value={"device_type": "qemu", "worker": "worker-01"}
    )
    mocker.patch(
        "lava_server.management.commands.sync.Command._parse_sync_dict", parse_sync_dict
    )

    out = StringIO()
    sys.stdout = out
    call_command("sync")
    assert (
        out.getvalue()
        == """Scanning devices:
* qemu01
  -> delete group permission: (change_device, foo)
"""
    )
