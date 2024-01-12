# Copyright (C) 2017 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import time

import pyudev

from lava_common.exceptions import InfrastructureError, LAVABug
from lava_dispatcher.action import Action


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
        wait_udev_event(match_dict=self.serial_device, subsystem="tty")
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
            match_dict=self.dfu_device, subsystem="usb", devtype="usb_device"
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
            match_dict=self.ms_device, subsystem="block", devtype="partition"
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
        wait_udev_event(devicepath=self.devicepath)
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

        wait_device_board_id = True
        if (
            "device_info" in self.job.device
            and type(self.job.device["device_info"]) is list
        ):
            wait_device_board_id = self.job.device["device_info"][0].get(
                "wait_device_board_id", True
            )

        if wait_device_board_id:
            self.logger.debug("Waiting for udev device with ID: %s", self.board_id)
            wait_udev_event(match_dict=self.udev_device)
        else:
            self.logger.debug(
                "Avoid waiting for udev device with ID: %s", self.board_id
            )
        return connection


def _dict_compare(d1, d2):
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    return {o for o in intersect_keys if d1[o] == d2[o]}


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


def wait_udev_event_setup(devicepath, devtype, match_dict, subsystem):
    """
    Setup pyudev internals for use by wait_udev_event and wait_udev_change_event methods
    :param devicepath:
    :param devtype:
    :param match_dict:
    :param subsystem:
    :return: (context, match_dict, monitor)
        context is a pyudev.Context instance
        match_dict from input parameter (initialized to dict if unset)
        monitor is pyudev.Monitor instance
    """
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
    return context, match_dict, monitor


def wait_udev_event(match_dict=None, subsystem=None, devtype=None, devicepath=None):
    context, match_dict, monitor = wait_udev_event_setup(
        devicepath, devtype, match_dict, subsystem
    )

    # Start to listen for events
    monitor.start()

    # Check if the device is already plugged-in
    for device in context.list_devices():
        if match(device, match_dict, devicepath):
            return

    # Wait for events.
    # Every events that happened since the call to start() will be handled now.
    match_dict["ACTION"] = "add"
    for device in iter(monitor.poll, None):
        if match(device, match_dict, devicepath):
            return


def wait_udev_changed_event(
    match_dict=None, subsystem=None, devtype=None, devicepath=None
):
    context, match_dict, monitor = wait_udev_event_setup(
        devicepath, devtype, match_dict, subsystem
    )

    # Start to listen for events
    monitor.start()
    match_dict["ACTION"] = "change"
    for device in iter(monitor.poll, None):
        if match(device, match_dict, devicepath):
            return


def get_udev_devices(job=None, logger=None, device_info=None, required=False):
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
        for udev_device in context.list_devices():
            udev_device_properties = udev_device.properties
            if board_id and usb_vendor_id and usb_product_id:
                if (
                    (udev_device_properties.get("ID_SERIAL_SHORT") == board_id)
                    and (udev_device_properties.get("ID_VENDOR_ID") == usb_vendor_id)
                    and (udev_device_properties.get("ID_MODEL_ID") == usb_product_id)
                ):
                    device_paths.add(udev_device.device_node)
                    added.add(board_id)
                    for child in udev_device.children:
                        if child.device_node:
                            device_paths.add(child.device_node)
                    for link in udev_device.device_links:
                        device_paths.add(link)
            elif board_id and usb_vendor_id and not usb_product_id:
                # try with parameters such as board id, usb_vendor_id
                if (udev_device_properties.get("ID_SERIAL_SHORT") == board_id) and (
                    udev_device_properties.get("ID_VENDOR_ID") == usb_vendor_id
                ):
                    device_paths.add(udev_device.device_node)
                    added.add(board_id)
                    for child in udev_device.children:
                        if child.device_node:
                            device_paths.add(child.device_node)
                    for link in udev_device.device_links:
                        device_paths.add(link)
            elif board_id and not usb_vendor_id and not usb_product_id:
                # try with board id alone
                if udev_device_properties.get("ID_SERIAL_SHORT") == board_id:
                    device_paths.add(udev_device.device_node)
                    added.add(board_id)
                    for child in udev_device.children:
                        if child.device_node:
                            device_paths.add(child.device_node)
                    for link in udev_device.device_links:
                        device_paths.add(link)
            elif usb_vendor_id and usb_product_id:
                # try with vendor and product id
                if (
                    udev_device_properties.get("ID_VENDOR_ID") == usb_vendor_id
                    and udev_device_properties.get("ID_MODEL_ID") == usb_product_id
                ):
                    device_paths.add(udev_device.device_node)
                    added.add(usb_product_id)
                    for child in udev_device.children:
                        if child.device_node:
                            device_paths.add(child.device_node)
                    for link in udev_device.device_links:
                        device_paths.add(link)
            elif usb_fs_label:
                # Just restrict by filesystem label.
                if udev_device_properties.get("ID_FS_LABEL") == usb_fs_label:
                    device_paths.add(udev_device.device_node)
                    added.add(usb_fs_label)
                    for child in udev_device.children:
                        if child.device_node:
                            device_paths.add(child.device_node)
                    for link in udev_device.device_links:
                        device_paths.add(link)
    if device_info and required:
        for static_device in device_info:
            for _, value in static_device.items():
                if value not in added:
                    raise InfrastructureError(
                        "Unable to add all static devices: board_id '%s' was not found"
                        % value
                    )
    device_paths = list(filter(None, device_paths))
    if logger and device_paths:
        logger.debug("Adding %s", ", ".join(device_paths))
    return device_paths


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
