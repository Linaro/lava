# Copyright (C) 2016 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
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

from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    InfrastructureError
)
from lava_dispatcher.pipeline.logical import Boot, RetryAction
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.utils.udev import WaitUSBSerialDeviceAction
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
import shutil
import os


class CMSIS(Boot):

    compatibility = 4  # FIXME: change this to 5 and update test cases

    def __init__(self, parent, parameters):
        super(CMSIS, self).__init__(parent)
        self.action = BootCMSIS()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'cmsis-dap' not in device['actions']['boot']['methods']:
            return False
        if 'method' not in parameters:
            return False
        if parameters['method'] != 'cmsis-dap':
            return False
        if 'board_id' not in device:
            return False
        if 'parameters' not in device['actions']['boot']['methods']['cmsis-dap']:
            return False
        if 'usb_mass_device' not in device['actions']['boot']['methods']['cmsis-dap']['parameters']:
            return False
        return True


class BootCMSIS(BootAction):

    def __init__(self):
        super(BootCMSIS, self).__init__()
        self.name = 'boot-cmsis'
        self.description = "boot cmsis usb image"
        self.summary = "boot cmsis usb image"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootCMSISRetry())


class BootCMSISRetry(RetryAction):

    def __init__(self):
        super(BootCMSISRetry, self).__init__()
        self.name = 'boot-cmsis-retry'
        self.description = "boot cmsis usb image with retry"
        self.summary = "boot cmsis usb image with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        method_params = self.job.device['actions']['boot']['methods']['cmsis-dap']['parameters']
        self.internal_pipeline.add_action(FlashCMSISAction())
        if method_params.get('resets_after_flash', True):
            self.internal_pipeline.add_action(WaitUSBSerialDeviceAction())
        self.internal_pipeline.add_action(ConnectDevice())


class FlashCMSISAction(Action):

    def __init__(self):
        super(FlashCMSISAction, self).__init__()
        self.name = "flash-cmsis"
        self.description = "flash cmsis to usb mass storage"
        self.summary = "flash cmsis to usb mass storage"
        self.filelist = []
        self.usb_mass_device = None

    def validate(self):
        super(FlashCMSISAction, self).validate()
        if self.job.device['board_id'] == '0000000000':
            self.errors = "board_id unset"
        method_parameters = self.job.device['actions']['boot']['methods']['cmsis-dap']['parameters']
        self.usb_mass_device = method_parameters.get('usb_mass_device', None)
        if not self.usb_mass_device:
            self.errors = "usb_mass_device unset"
        if not os.path.exists(self.usb_mass_device):
            self.errors = "usb_mass_device does not exist %s" % self.usb_mass_device
        namespace = self.parameters['namespace']
        for action in self.data[namespace]['download_action'].keys():
            action_arg = self.get_namespace_data(action='download_action', label=action, key='file')
            self.filelist.extend([action_arg])

    def run(self, connection, max_end_time, args=None):
        connection = super(FlashCMSISAction, self).run(connection, max_end_time, args)
        dstdir = mkdtemp()
        mount_command = "mount -t vfat %s %s" % (self.usb_mass_device, dstdir)
        self.run_command(mount_command.split(' '), allow_silent=True)
        # mount
        for f in self.filelist:
            self.logger.debug("Copying %s to %s", f, dstdir)
            shutil.copy2(f, dstdir)
        # umount
        umount_command = "umount %s" % self.usb_mass_device
        self.run_command(umount_command.split(' '), allow_silent=True)
        if self.errors:
            raise InfrastructureError("Unable to (un)mount USB device: %s" % self.usb_mass_device)
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        return connection
