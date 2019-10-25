# Copyright (C) 2017 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import pyudev
import time
from lava_dispatcher.action import Action
from lava_common.exceptions import LAVABug, InfrastructureError


class WaitUSBSerialDeviceAction(Action):

    name = "wait-usb-serial"
    description = "wait for USB serial device"
    summary = "wait for USB serial device"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.serial_device = {}
        self.usb_sleep = 0

    def validate(self):
        super().validate()
        board_id = self.job.device.get("board_id", "")
        usb_vendor_id = self.job.device.get("usb_vendor_id", "")
        usb_product_id = self.job.device.get("usb_product_id", "")
        usb_serial_driver = self.job.device.get("usb_serial_driver", "cdc_acm")
        if board_id == "0000000000":
            self.errors = "[USBSERIAL] board_id unset"
        if usb_vendor_id == "0000":
            self.errors = "usb_vendor_id unset"
        if usb_product_id == "0000":
            self.errors = "usb_product_id unset"
        self.serial_device = {
            "ID_SERIAL_SHORT": str(board_id),
            "ID_VENDOR_ID": str(usb_vendor_id),
            "ID_MODEL_ID": str(usb_product_id),
            "ID_USB_DRIVER": str(usb_serial_driver),
        }
        self.usb_sleep = self.job.device.get("usb_sleep", 0)
        if not isinstance(self.usb_sleep, int):
            self.errors = "usb_sleep should be an integer"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        self.logger.debug("Waiting for usb serial device: %s", self.serial_device)
        wait_udev_event(action="add", match_dict=self.serial_device, subsystem="tty")
        if self.usb_sleep:
            self.logger.debug(
                "Waiting for the board to setup, sleeping %ds", self.usb_sleep
            )
            time.sleep(self.usb_sleep)
        return connection


class WaitDFUDeviceAction(Action):

    name = "wait-dfu-device"
    description = "wait for DFU device"
    summary = "wait for DFU device"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.dfu_device = {}

    def validate(self):
        super().validate()
        board_id = self.job.device.get("board_id", "")
        usb_vendor_id = self.job.device.get("usb_vendor_id", "")
        usb_product_id = self.job.device.get("usb_product_id", "")
        if board_id == "0000000000":
            self.errors = "[DFU] board_id unset"
        if usb_vendor_id == "0000":
            self.errors = "usb_vendor_id unset"
        if usb_product_id == "0000":
            self.errors = "usb_product_id unset"
        self.dfu_device = {
            "ID_SERIAL_SHORT": str(board_id),
            "ID_VENDOR_ID": str(usb_vendor_id),
            "ID_MODEL_ID": str(usb_product_id),
        }

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        self.logger.debug("Waiting for DFU device: %s", self.dfu_device)
        wait_udev_event(
            action="add",
            match_dict=self.dfu_device,
            subsystem="usb",
            devtype="usb_device",
        )
        return connection


class WaitUSBMassStorageDeviceAction(Action):

    name = "wait-usb-mass-storage-device"
    description = "wait for USB mass storage device"
    summary = "wait for USB mass storage device"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.ms_device = {}

    def validate(self):
        super().validate()
        usb_fs_label = self.job.device.get("usb_filesystem_label")
        if not isinstance(usb_fs_label, str):
            self.errors = "usb_fs_label unset"
        self.ms_device = {"ID_FS_LABEL": str(usb_fs_label)}

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        self.logger.debug("Waiting for USB mass storage device: %s", self.ms_device)
        wait_udev_event(
            action="add",
            match_dict=self.ms_device,
            subsystem="block",
            devtype="partition",
        )
        return connection


class WaitDevicePathAction(Action):

    name = "wait-device-path"
    description = "wait for udev device path"
    summary = "wait for udev device path"
    timeout_exception = InfrastructureError

    def __init__(self, path=None):
        super().__init__()
        self.devicepath = path

    def validate(self):
        super().validate()
        if not isinstance(self.devicepath, str):
            self.errors = "invalid device path"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        self.logger.debug("Waiting for udev device path: %s", self.devicepath)
        wait_udev_event(action="add", devicepath=self.devicepath)
        return connection


class WaitDeviceBoardID(Action):

    name = "wait-device-boardid"
    description = "wait for udev device with board ID"
    summary = "wait for udev device with board ID"
    timeout_exception = InfrastructureError

    def __init__(self, board_id=None):
        super().__init__()
        self.udev_device = None
        if not board_id:
            self.board_id = self.job.device.get("board_id")
        else:
            self.board_id = board_id

    def validate(self):
        super().validate()
        if not isinstance(self.board_id, str):
            self.errors = "invalid board_id"
        self.udev_device = {"ID_SERIAL_SHORT": str(self.board_id)}

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        self.logger.debug("Waiting for udev device with ID: %s", self.board_id)
        wait_udev_event(action="add", match_dict=self.udev_device)
        return connection


def _dict_compare(d1, d2):  # pylint: disable=invalid-name
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    return set(o for o in intersect_keys if d1[o] == d2[o])


def match(device, match_dict, devicepath):
    same = _dict_compare(dict(device), match_dict)
    if same == set(match_dict.keys()):
        if devicepath:
            if devicepath in dict(device).get("DEVLINKS", "") or devicepath in dict(
                device
            ).get("DEVNAME", ""):
                return True
        else:
            return True
    return False


def wait_udev_event(
    action="add", match_dict=None, subsystem=None, devtype=None, devicepath=None
):
    if action not in ["add", "remove", "change"]:
        raise LAVABug(
            "Invalid action for udev to wait for: %s, expected 'add' or 'remove'"
            % action
        )
    if match_dict:
        if not isinstance(match_dict, dict):
            raise LAVABug("match_dict was not a dict")
    else:
        if devicepath:
            if not isinstance(devicepath, str):
                raise LAVABug("devicepath was not a string")
            match_dict = {}
        else:
            raise LAVABug("Neither match_dict nor devicepath were set")
    if devtype and not subsystem:
        raise LAVABug("Cannot filter udev by devtype without a subsystem")

    # Create and configure the monitor
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    if devtype and subsystem:
        monitor.filter_by(subsystem, devtype)
    else:
        if subsystem:
            monitor.filter_by(subsystem)

    # Start to listen for events
    monitor.start()

    # Check if the device is already plugged-in
    for device in context.list_devices():
        if match(device, match_dict, devicepath):
            return

    # Wait for events.
    # Every events that happened since the call to start() will be handled now.
    match_dict["ACTION"] = action
    for device in iter(monitor.poll, None):
        if match(device, match_dict, devicepath):
            return


def get_udev_devices(job=None, logger=None, device_info=None):
    """
    Get udev device nodes based on serial, vendor and product ID
    All subsystems are allowed so that additional hardware like
    tty devices can be added to the LXC. The ID to match is controlled
    by the lab admin.
    """
    context = pyudev.Context()
    device_paths = set()
    devices = []
    if job:
        devices = job.device.get("device_info", [])
    # device_info argument overrides job device_info
    if device_info:
        devices = device_info
    if not devices:
        return []
    added = set()
    for usb_device in devices:
        board_id = str(usb_device.get("board_id", ""))
        usb_vendor_id = str(usb_device.get("usb_vendor_id", ""))
        usb_product_id = str(usb_device.get("usb_product_id", ""))
        usb_fs_label = str(usb_device.get("fs_label", ""))
        # check if device is already connected
        # try with all parameters such as board id, usb_vendor_id and
        # usb_product_id
        for device in context.list_devices():
            if board_id and usb_vendor_id and usb_product_id:
                if (
                    (device.get("ID_SERIAL_SHORT") == board_id)
                    and (device.get("ID_VENDOR_ID") == usb_vendor_id)
                    and (device.get("ID_MODEL_ID") == usb_product_id)
                ):
                    device_paths.add(device.device_node)
                    added.add(board_id)
                    for child in device.children:
                        if child.device_node:
                            device_paths.add(child.device_node)
                    for link in device.device_links:
                        device_paths.add(link)
            elif board_id and usb_vendor_id and not usb_product_id:
                # try with parameters such as board id, usb_vendor_id
                if (device.get("ID_SERIAL_SHORT") == board_id) and (
                    device.get("ID_VENDOR_ID") == usb_vendor_id
                ):
                    device_paths.add(device.device_node)
                    added.add(board_id)
                    for child in device.children:
                        if child.device_node:
                            device_paths.add(child.device_node)
                    for link in device.device_links:
                        device_paths.add(link)
            elif board_id and not usb_vendor_id and not usb_product_id:
                # try with board id alone
                if device.get("ID_SERIAL_SHORT") == board_id:
                    device_paths.add(device.device_node)
                    added.add(board_id)
                    for child in device.children:
                        if child.device_node:
                            device_paths.add(child.device_node)
                    for link in device.device_links:
                        device_paths.add(link)
            elif usb_fs_label:
                # Just restrict by filesystem label.
                if device.get("ID_FS_LABEL") == usb_fs_label:
                    device_paths.add(device.device_node)
                    added.add(usb_fs_label)
                    for child in device.children:
                        if child.device_node:
                            device_paths.add(child.device_node)
                    for link in device.device_links:
                        device_paths.add(link)
    if device_info:
        for static_device in device_info:
            for _, value in static_device.items():
                if value not in added:
                    raise InfrastructureError(
                        "Unable to add all static devices: board_id '%s' was not found"
                        % value
                    )
    if logger and device_paths:
        logger.debug("Adding %s", ", ".join(device_paths))
    return list(device_paths)


def allow_fs_label(device):
    # boot/deploy methods that indicate that the device in question
    # will require a filesystem label to identify a device.
    # So far, mps devices are supported, but these don't provide a
    # unique serial, so fs label must be used.
    fs_label_methods = ["mps", "recovery"]

    # Don't allow using filesystem labels by default as they are
    # unreliable, and can be changed via a malicious job.
    _allow_fs_label = False
    for method in fs_label_methods:
        if (
            method in device["actions"]["boot"]["methods"]
            or method in device["actions"]["deploy"]["methods"]
        ):
            _allow_fs_label = True
    return _allow_fs_label


def lxc_udev_rule(data):
    """Construct the udev rule string."""
    rule = 'ACTION=="add", '
    if data["serial_number"]:
        rule += 'ATTR{{serial}}=="{serial_number}", '
    if data["vendor_id"] is not None:
        rule += 'ATTR{{idVendor}}=="{vendor_id}", '
    if data["product_id"] is not None:
        rule += 'ATTR{{idProduct}}=="{product_id}", '
    if data["fs_label"] is not None:
        rule += 'ENV{{ID_FS_LABEL}}=="{fs_label}", '
    rule += (
        'RUN+="/usr/share/lava-dispatcher/lava_lxc_device_add.py '
        "--lxc-name {lxc_name} --device-node $name "
        "--job-id {job_id}"
    )
    if data["logging_url"]:
        rule += " --logging-url {logging_url}"
    rule = rule.format(**data)

    if data["master_cert"] is not None:
        rule += " --master-cert %s" % data["master_cert"]
    if data["slave_cert"] is not None:
        rule += " --slave-cert %s" % data["slave_cert"]
    if data["socks_proxy"] is not None:
        rule += " --socks-proxy %s" % data["socks_proxy"]
    if data["ipv6"]:
        rule += " --ipv6"
    if data["fs_label"] is not None:
        rule = 'IMPORT{builtin}="blkid"\n' + rule
    rule += '"\n'
    return rule


def lxc_udev_rule_parent(data):
    """Construct the udev rule string."""
    rule = 'ACTION=="add", '
    if data["vendor_id"] is not None:
        rule += 'ATTRS{{idVendor}}=="{vendor_id}", '
    if data["product_id"] is not None:
        rule += 'ATTRS{{idProduct}}=="{product_id}", '
    if data["fs_label"] is not None:
        rule += 'ENV{{ID_FS_LABEL}}=="{fs_label}", '
    rule += (
        'RUN+="/usr/share/lava-dispatcher/lava_lxc_device_add.py '
        "--lxc-name {lxc_name} --device-node $name "
        "--job-id {job_id}"
    )
    if data["logging_url"]:
        rule += " --logging-url {logging_url}"
    rule = rule.format(**data)

    if data["master_cert"] is not None:
        rule += " --master-cert %s" % data["master_cert"]
    if data["slave_cert"] is not None:
        rule += " --slave-cert %s" % data["slave_cert"]
    if data["socks_proxy"] is not None:
        rule += " --socks-proxy %s" % data["socks_proxy"]
    if data["ipv6"]:
        rule += " --ipv6"
    if data["fs_label"] is not None:
        rule = 'IMPORT{builtin}="blkid"\n' + rule
    rule += '"\n'
    return rule
