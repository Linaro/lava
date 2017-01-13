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


def get_usb_devices(job):
    context = pyudev.Context()
    device_paths = set()
    for usb_device in job.device.get('device_info', []):
        board_id = str(usb_device.get('board_id', ''))
        usb_vendor_id = str(usb_device.get('usb_vendor_id', ''))
        usb_product_id = str(usb_device.get('usb_product_id', ''))
        # check if device is already connected
        # try with all parameters such as board id, usb_vendor_id and
        # usb_product_id
        for device in context.list_devices():
            if (device.get('ID_SERIAL_SHORT') == board_id) \
               and (device.get('ID_VENDOR_ID') == usb_vendor_id) \
               and (device.get('ID_MODEL_ID') == usb_product_id):
                device_paths.add(device.device_node)
        # try with parameters such as board id, usb_vendor_id
        for device in context.list_devices():
            if (device.get('ID_SERIAL_SHORT') == board_id) \
               and (device.get('ID_VENDOR_ID') == usb_vendor_id):
                device_paths.add(device.device_node)
        # try with board id alone
        for device in context.list_devices():
            if device.get('ID_SERIAL_SHORT') == board_id:
                device_paths.add(device.device_node)
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
        if board_id and usb_vendor_id:
            for device in iter(monitor.poll, None):
                if (device.get('ID_SERIAL_SHORT') == board_id) \
                   and (device.get('ID_VENDOR_ID') == usb_vendor_id) \
                   and device.action in device_actions:
                    break
            return
        if board_id:
            for device in iter(monitor.poll, None):
                if (device.get('ID_SERIAL_SHORT') == board_id) \
                   and device.action in device_actions:
                    break
            return
