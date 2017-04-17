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
import logging
from lava_dispatcher.pipeline.action import Action, LAVABug


class WaitUSBSerialDeviceAction(Action):

    def __init__(self):
        super(WaitUSBSerialDeviceAction, self).__init__()
        self.name = "wait-usb-serial"
        self.description = "wait for USB serial device"
        self.summary = self.description
        self.serial_device = {}

    def validate(self):
        super(WaitUSBSerialDeviceAction, self).validate()
        board_id = self.job.device.get('board_id', '')
        usb_vendor_id = self.job.device.get('usb_vendor_id', '')
        usb_product_id = self.job.device.get('usb_product_id', '')
        usb_serial_driver = self.job.device.get('usb_serial_driver', 'cdc_acm')
        if board_id == '0000000000':
            self.errors = "board_id unset"
        if usb_vendor_id == '0000':
            self.errors = 'usb_vendor_id unset'
        if usb_product_id == '0000':
            self.errors = 'usb_product_id unset'
        self.serial_device = {'ID_SERIAL_SHORT': str(board_id),
                              'ID_VENDOR_ID': str(usb_vendor_id),
                              'ID_MODEL_ID': str(usb_product_id),
                              'ID_USB_DRIVER': str(usb_serial_driver)}

    def run(self, connection, max_end_time, args=None):
        connection = super(WaitUSBSerialDeviceAction, self).run(connection, max_end_time, args)
        self.logger.debug("Waiting for usb serial device: %s", self.serial_device)
        wait_udev_event(action='add', match_dict=self.serial_device, subsystem='tty')
        return connection


class WaitDFUDeviceAction(Action):

    def __init__(self):
        super(WaitDFUDeviceAction, self).__init__()
        self.name = "wait-dfu-device"
        self.description = "wait for DFU device"
        self.summary = self.description
        self.dfu_device = {}

    def validate(self):
        super(WaitDFUDeviceAction, self).validate()
        board_id = self.job.device.get('board_id', '')
        usb_vendor_id = self.job.device.get('usb_vendor_id', '')
        usb_product_id = self.job.device.get('usb_product_id', '')
        if board_id == '0000000000':
            self.errors = "board_id unset"
        if usb_vendor_id == '0000':
            self.errors = 'usb_vendor_id unset'
        if usb_product_id == '0000':
            self.errors = 'usb_product_id unset'
        self.dfu_device = {'ID_SERIAL_SHORT': str(board_id),
                           'ID_VENDOR_ID': str(usb_vendor_id),
                           'ID_MODEL_ID': str(usb_product_id)}

    def run(self, connection, max_end_time, args=None):
        connection = super(WaitDFUDeviceAction, self).run(connection, max_end_time, args)
        self.logger.debug("Waiting for DFU device: %s", self.dfu_device)
        wait_udev_event(action='add', match_dict=self.dfu_device, subsystem='usb', devtype='usb_device')
        return connection


class WaitUSBMassStorageDeviceAction(Action):

    def __init__(self):
        super(WaitUSBMassStorageDeviceAction, self).__init__()
        self.name = "wait-usb-mass-storage-device"
        self.description = "wait for USB mass storage device"
        self.summary = self.description
        self.ms_device = {}

    def validate(self):
        super(WaitUSBMassStorageDeviceAction, self).validate()
        board_id = self.job.device.get('board_id', '')
        usb_vendor_id = self.job.device.get('usb_vendor_id', '')
        usb_product_id = self.job.device.get('usb_product_id', '')
        usb_fs_label = self.job.device.get('usb_filesystem_label', None)
        if board_id == '0000000000':
            self.errors = "board_id unset"
        if usb_vendor_id == '0000':
            self.errors = 'usb_vendor_id unset'
        if usb_product_id == '0000':
            self.errors = 'usb_product_id unset'
        if not isinstance(usb_fs_label, str):
            self.errors = 'usb_fs_label unset'
        self.ms_device = {'ID_SERIAL_SHORT': str(board_id),
                          'ID_VENDOR_ID': str(usb_vendor_id),
                          'ID_MODEL_ID': str(usb_product_id),
                          'ID_FS_LABEL': str(usb_fs_label)}

    def run(self, connection, max_end_time, args=None):
        connection = super(WaitUSBMassStorageDeviceAction, self).run(connection, max_end_time, args)
        self.logger.debug("Waiting for USB mass storage device: %s", self.ms_device)
        wait_udev_event(action='add', match_dict=self.ms_device, subsystem='block', devtype='partition')
        return connection


def _dict_compare(d1, d2):  # pylint: disable=invalid-name
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    return set(o for o in intersect_keys if d1[o] == d2[o])


def wait_udev_event(action='add', match_dict=None, subsystem=None, devtype=None):
    if action not in ['add', 'remove']:
        raise LAVABug("Invalid action for udev to wait for: %s, expected 'add' or 'remove'" % action)
    if match_dict:
        if isinstance(match_dict, dict):
            if match_dict == {}:
                raise LAVABug("Trying to match udev event with empty match_dict")
        else:
            raise LAVABug("match_dict was not a dict")
    else:
        raise LAVABug("match_dict was None")
    if devtype and not subsystem:
        raise LAVABug("Cant filter udev by devtype without a subsystem")
    match_dict['ACTION'] = action
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    if devtype and subsystem:
        monitor.filter_by(subsystem, devtype)
    else:
        if subsystem:
            monitor.filter_by(subsystem)
    for device in iter(monitor.poll, None):
        same = _dict_compare(dict(device), match_dict)
        if same == set(match_dict.keys()):
            break


def get_usb_devices(job, logger=None):
    context = pyudev.Context()
    device_paths = set()
    for usb_device in job.device.get('device_info', []):
        board_id = str(usb_device.get('board_id', ''))
        usb_vendor_id = str(usb_device.get('usb_vendor_id', ''))
        usb_product_id = str(usb_device.get('usb_product_id', ''))
        # check if device is already connected
        # try with all parameters such as board id, usb_vendor_id and
        # usb_product_id
        for device in context.list_devices(subsystem='usb'):
            if board_id and usb_vendor_id and usb_product_id:
                if (device.get('ID_SERIAL_SHORT') == board_id) \
                   and (device.get('ID_VENDOR_ID') == usb_vendor_id) \
                   and (device.get('ID_MODEL_ID') == usb_product_id):
                    device_paths.add(device.device_node)
            elif board_id and usb_vendor_id and not usb_product_id:
                # try with parameters such as board id, usb_vendor_id
                if (device.get('ID_SERIAL_SHORT') == board_id) \
                   and (device.get('ID_VENDOR_ID') == usb_vendor_id):
                    device_paths.add(device.device_node)
            elif board_id and not usb_vendor_id and not usb_product_id:
                # try with board id alone
                if device.get('ID_SERIAL_SHORT') == board_id:
                    device_paths.add(device.device_node)
    if logger and device_paths:
        logger.debug("Adding %s", ', '.join(device_paths))
    return list(device_paths)


def usb_device_wait(job, device_actions=None):
    context = pyudev.Context()
    if device_actions is None:
        device_actions = []
    for usb_device in job.device.get('device_info', []):
        board_id = str(usb_device.get('board_id', ''))
        usb_vendor_id = str(usb_device.get('usb_vendor_id', ''))
        usb_product_id = str(usb_device.get('usb_product_id', ''))
        # monitor for device
        monitor = pyudev.Monitor.from_netlink(context)
        if board_id and usb_vendor_id and usb_product_id:
            for device in iter(monitor.poll, None):
                if (device.get('ID_SERIAL_SHORT') == board_id) \
                   and (device.get('ID_VENDOR_ID') == usb_vendor_id) \
                   and (device.get('ID_MODEL_ID') == usb_product_id) \
                   and device.action in device_actions:
                    break
            return
        elif board_id and usb_vendor_id and not usb_product_id:
            for device in iter(monitor.poll, None):
                if (device.get('ID_SERIAL_SHORT') == board_id) \
                   and (device.get('ID_VENDOR_ID') == usb_vendor_id) \
                   and device.action in device_actions:
                    break
            return
        elif board_id and not usb_vendor_id and not usb_product_id:
            for device in iter(monitor.poll, None):
                if (device.get('ID_SERIAL_SHORT') == board_id) \
                   and device.action in device_actions:
                    break
            return
