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
    InfrastructureError,
)
from lava_dispatcher.pipeline.logical import Boot, RetryAction
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.boot import WaitUSBDeviceAction
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.power import PowerOn
from lava_dispatcher.pipeline.utils.shell import which
from lava_dispatcher.pipeline.utils.strings import substitute


class DFU(Boot):

    compatibility = 4  # FIXME: change this to 5 and update test cases

    def __init__(self, parent, parameters):
        super(DFU, self).__init__(parent)
        self.action = BootDFU()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'dfu' not in device['actions']['boot']['methods']:
            return False
        if 'method' not in parameters:
            return False
        if parameters['method'] != 'dfu':
            return False
        if 'board_id' not in device:
            return False
        return True


class BootDFU(BootAction):

    def __init__(self):
        super(BootDFU, self).__init__()
        self.name = 'boot-dfu-image'
        self.description = "boot monitored dfu image with retry"
        self.summary = "boot monitor with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootDFURetry())


class BootDFURetry(RetryAction):

    def __init__(self):
        super(BootDFURetry, self).__init__()
        self.name = 'boot-dfu-retry'
        self.description = "boot dfu image using the command line interface"
        self.summary = "boot dfu image"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(PowerOn())
        self.internal_pipeline.add_action(WaitUSBDeviceAction(
            device_actions=['add']))
        self.internal_pipeline.add_action(FlashDFUAction())


class FlashDFUAction(Action):

    def __init__(self):
        super(FlashDFUAction, self).__init__()
        self.name = "flash-dfu"
        self.description = "use dfu to flash the images"
        self.summary = "use dfu to flash the images"
        self.base_command = []
        self.exec_list = []
        self.board_id = '0000000000'
        self.usb_vendor_id = '0000'
        self.usb_product_id = '0000'

    def validate(self):
        super(FlashDFUAction, self).validate()
        try:
            boot = self.job.device['actions']['boot']['methods']['dfu']
            dfu_binary = which(boot['parameters']['command'])
            self.base_command = [dfu_binary]
            self.base_command.extend(boot['parameters'].get('options', []))
            if self.job.device['board_id'] == '0000000000':
                self.errors = "board_id unset"
            if self.job.device['usb_vendor_id'] == '0000':
                self.errors = 'usb_vendor_id unset'
            if self.job.device['usb_product_id'] == '0000':
                self.errors = 'usb_product_id unset'
            self.usb_vendor_id = self.job.device['usb_vendor_id']
            self.usb_product_id = self.job.device['usb_product_id']
            self.board_id = self.job.device['board_id']
            self.base_command.extend(['--serial', self.board_id])
            self.base_command.extend(['--device', '%s:%s' % (self.usb_vendor_id, self.usb_product_id)])
        except AttributeError as exc:
            raise InfrastructureError(exc)
        except (KeyError, TypeError):
            self.errors = "Invalid parameters for %s" % self.name
        substitutions = {}
        namespace = self.parameters['namespace']
        for action in self.data[namespace]['download_action'].keys():
            dfu_full_command = []
            image_arg = self.data[namespace]['download_action'][action].get('image_arg', None)
            action_arg = self.data[namespace]['download_action'][action].get('file', None)
            if not image_arg or not action_arg:
                self.errors = "Missing image_arg for %s. " % action
                continue
            substitutions["{%s}" % action] = action_arg
            dfu_full_command.extend(self.base_command)
            dfu_full_command.extend(substitute([image_arg], substitutions))
            self.exec_list.append(dfu_full_command)
        if len(self.exec_list) < 1:
            self.errors = "No DFU command to execute"

    def run(self, connection, max_end_time, args=None):
        count = 1
        for dfu_command in self.exec_list:
            if count == (len(self.exec_list)):
                if self.job.device['actions']['boot']['methods']['dfu'].get('reset_works', True):
                    dfu_command.extend(['--reset'])
            dfu = ' '.join(dfu_command)
            output = self.run_command(dfu.split(' '))
            if output:
                if not ("No error condition is present\nDone!\n" in output):
                    error = "command failed: %s" % dfu
                    self.errors = error
            else:
                error = "command failed: %s" % dfu
                self.errors = error
            count += 1
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        return connection
