# Copyright (C) 2019 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from argparse import Namespace

import pytest

import lava_dispatcher_host
from lava_common.exceptions import InfrastructureError
from lava_common.yaml import yaml_safe_load
from lava_dispatcher_host import (
    add_device_container_mapping,
    load_mapping_data,
    share_device_with_container,
)


@pytest.fixture(autouse=True)
def setup(monkeypatch, mocker, tmp_path):
    os.makedirs(tmp_path / "1")
    os.makedirs(tmp_path / "2")
    monkeypatch.setattr(lava_dispatcher_host, "JOBS_DIR", str(tmp_path))
    mocker.patch("os.path.exists", return_value=True)


def test_simple_mapping(tmp_path):
    device_info = {"foo": "bar"}
    add_device_container_mapping("1", device_info, "mycontainer")
    with open(tmp_path / "1" / "usbmap.yaml") as f:
        data = yaml_safe_load(f)[0]

    assert data["device_info"] == device_info
    assert data["container"] == "mycontainer"
    assert data["container_type"] == "lxc"


def test_add_mapping_without_job_dir(tmp_path):
    os.rmdir(tmp_path / "1")
    add_device_container_mapping("1", {"foo": "bar"}, "mycontainer")
    assert os.path.exists(tmp_path / "1" / "usbmap.yaml")


def test_device_info_required(mocker):
    with pytest.raises(ValueError):
        add_device_container_mapping("1", {}, "mycontainer")


def test_device_info_keys_required(mocker):
    with pytest.raises(ValueError):
        add_device_container_mapping("1", {"serial_number": None}, "mycontainer")


@pytest.fixture
def device_links(pyudev):
    return pyudev.Devices.from_device_file.return_value.device_links


@pytest.fixture
def pass_device_lxc(mocker):
    return mocker.patch("lava_dispatcher_host.pass_device_into_container_lxc")


def test_simple_share_device_with_container(mocker, pass_device_lxc, device_links):
    add_device_container_mapping("1", {"serial_number": "1234567890"}, "mycontainer")
    share_device_with_container(Namespace(device="foo/bar", serial_number="1234567890"))
    pass_device_lxc.assert_called_once_with(
        "mycontainer", "/dev/foo/bar", device_links, "1"
    )


def test_mapping_with_serial_number_but_called_with_vendor_product_id_too(
    mocker, pass_device_lxc, device_links
):
    add_device_container_mapping(
        "1",
        {
            "serial_number": "1234567890",
            "vendor_id": None,
            "product_id": None,
            "fs_label": None,
        },
        "mycontainer",
    )
    share_device_with_container(
        Namespace(
            device="foo/bar",
            serial_number="1234567890",
            vendor_id="0123",
            product_id="4567",
        )
    )

    pass_device_lxc.assert_called_once_with(
        "mycontainer", "/dev/foo/bar", device_links, "1"
    )


def test_two_concurrent_jobs(mocker, pass_device_lxc, device_links):
    add_device_container_mapping("1", {"serial_number": "1234567890"}, "container1")
    add_device_container_mapping("2", {"serial_number": "9876543210"}, "container2")
    share_device_with_container(Namespace(device="baz/qux", serial_number="9876543210"))

    pass_device_lxc.assert_called_once_with(
        "container2", "/dev/baz/qux", device_links, "2"
    )


def test_no_device_found(mocker):
    check_call = mocker.patch("subprocess.check_call")
    share_device_with_container(
        Namespace(device="bus/usb/001/099", serial_number="9876543210")
    )
    check_call.assert_not_called()


def test_map_by_vendor_id_and_product_id(mocker, pass_device_lxc, device_links):
    add_device_container_mapping(
        "1", {"vendor_id": "aaaa", "product_id": "xxxx"}, "container1"
    )
    share_device_with_container(
        Namespace(
            device="bus/usb/001/099",
            serial_number="9876543210",
            vendor_id="aaaa",
            product_id="xxxx",
        )
    )
    pass_device_lxc.assert_called_once_with(
        "container1", "/dev/bus/usb/001/099", device_links, "1"
    )


def test_device_missing(mocker):
    mocker.patch("os.path.exists", return_value=False)
    check_call = mocker.patch("subprocess.check_call")
    add_device_container_mapping("1", {"serial_number": "1234567890"}, "mycontainer")
    share_device_with_container(Namespace(device="foo/bar", serial_number="1234567890"))
    check_call.assert_not_called()


def test_unknown_container_type(mocker):
    add_device_container_mapping(
        "1",
        {"serial_number": "1234567890"},
        "mycontainer",
        container_type="unsupported",
    )
    with pytest.raises(InfrastructureError):
        share_device_with_container(
            Namespace(device="foo/bar", serial_number="1234567890")
        )


def test_only_adds_slash_dev_if_needed(mocker):
    share = mocker.patch("lava_dispatcher_host.share_device_with_container_lxc")
    add_device_container_mapping("1", {"serial_number": "1234567890"}, "mycontainer")
    share_device_with_container(
        Namespace(device="/dev/foo/bar", serial_number="1234567890")
    )
    share.assert_called_once_with("mycontainer", "/dev/foo/bar", job_id="1")


def test_second_mapping_does_not_invalidate_first(mocker):
    share = mocker.patch("lava_dispatcher_host.share_device_with_container_lxc")
    add_device_container_mapping("1", {"serial_number": "1234567890"}, "mycontainer1")
    add_device_container_mapping("1", {"serial_number": "badbeeb00c"}, "mycontainer1")
    share_device_with_container(
        Namespace(device="/dev/foo/bar", serial_number="1234567890")
    )
    share.assert_called_once_with("mycontainer1", "/dev/foo/bar", job_id="1")


def test_two_devices_two_containers(mocker):
    share = mocker.patch("lava_dispatcher_host.share_device_with_container_lxc")
    add_device_container_mapping("1", {"serial_number": "1234567890"}, "mycontainer1")
    add_device_container_mapping("1", {"serial_number": "badbeeb00c"}, "mycontainer2")
    share_device_with_container(
        Namespace(device="/dev/foo/bar", serial_number="1234567890")
    )
    share.assert_called_once_with("mycontainer1", "/dev/foo/bar", job_id="1")
    share.reset_mock()

    share_device_with_container(
        Namespace(device="/dev/foo/bar", serial_number="badbeeb00c")
    )
    share.assert_called_once_with("mycontainer2", "/dev/foo/bar", job_id="1")


def test_device_plus_parent(mocker):
    share = mocker.patch("lava_dispatcher_host.share_device_with_container_lxc")
    add_device_container_mapping(
        "1",
        {
            "serial_number": "1234567890",
            "vendor_id": None,
            "product_id": None,
            "fs_label": None,
        },
        "mycontainer1",
    )
    add_device_container_mapping(
        "1",
        {
            "serial_number": "",
            "vendor_id": "1234",
            "product_id": "3456",
            "fs_label": None,
        },
        "mycontainer2",
    )

    share_device_with_container(
        Namespace(device="/dev/foo/bar", serial_number="1234567890")
    )
    share.assert_called_once_with("mycontainer1", "/dev/foo/bar", job_id="1")
    share.reset_mock()

    share_device_with_container(
        Namespace(device="/dev/foo/bar", vendor_id="1234", product_id="3456")
    )
    share.assert_called_once_with("mycontainer2", "/dev/foo/bar", job_id="1")
    share.reset_mock()


def test_mapping_for_new_container_overrides_previous_mapping(tmp_path):
    add_device_container_mapping(
        "1",
        {
            "serial_number": "1234567890",
            "vendor_id": None,
            "product_id": None,
            "fs_label": None,
        },
        "mycontainer1",
    )
    add_device_container_mapping(
        "1",
        {
            "serial_number": "1234567890",
            "vendor_id": None,
            "product_id": None,
            "fs_label": None,
        },
        "mycontainer2",
    )
    with open(tmp_path / "1" / "usbmap.yaml") as f:
        data = yaml_safe_load(f)
    assert len(data) == 1
    assert data[0]["container"] == "mycontainer2"


class TestLoadMapping:
    @pytest.fixture
    def mapping(self, tmp_path):
        return tmp_path / "usbmap.yaml"

    def test_empty(self, mapping):
        mapping.write_text("")
        data = load_mapping_data(mapping)
        assert type(data) is list

    def test_missing(self, mapping):
        assert not mapping.exists()
        data = load_mapping_data(mapping)
        assert type(data) is list
