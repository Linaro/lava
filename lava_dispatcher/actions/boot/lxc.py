# Copyright (C) 2015 Linaro Limited
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

import time
from lava_dispatcher.action import (
    Pipeline,
    Action,
    JobError,
)
from lava_dispatcher.logical import Boot
from lava_dispatcher.actions.boot import BootAction
from lava_dispatcher.actions.boot.environment import (
    ExportDeviceEnvironment,
)
from lava_dispatcher.connections.lxc import (
    ConnectLxc,
)
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.shell import infrastructure_error
from lava_dispatcher.utils.udev import get_udev_devices


class BootLxc(Boot):
    """
    Attaches to the lxc container.
    """
    compatibility = 1

    def __init__(self, parent, parameters):
        super(BootLxc, self).__init__(parent)
        self.action = BootLxcAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' in parameters:
            if parameters['method'] == 'lxc':
                return True, 'accepted'
        return False, '"method" was not in parameters or "method" was not "lxc"'


class BootLxcAction(BootAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the
    connection after boot.
    """
    def __init__(self):
        super(BootLxcAction, self).__init__()
        self.name = "lxc-boot"
        self.summary = "lxc boot"
        self.description = "lxc boot into the system"

    def validate(self):
        super(BootLxcAction, self).validate()

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(LxcStartAction())
        self.internal_pipeline.add_action(LxcAddStaticDevices())
        self.internal_pipeline.add_action(ConnectLxc())
        # Skip AutoLoginAction unconditionally as this action tries to parse kernel message
        # self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(ExportDeviceEnvironment())


class LxcAddStaticDevices(Action):
    """
    Identifies permanently powered devices which are relevant
    to this LXC and adds the devices to the LXC after startup.
    e.g. Devices providing a tty are often powered from the
    worker.
    """

    def __init__(self):
        super(LxcAddStaticDevices, self).__init__()
        self.name = 'lxc-add-static'
        self.description = 'Add devices which are permanently powered by the worker to the LXC'
        self.summary = 'Add static devices to the LXC'

    def validate(self):
        super(LxcAddStaticDevices, self).validate()
        # If there is no static_info then this action should be idempotent.
        try:
            if 'static_info' in self.job.device:
                for usb_device in self.job.device['static_info']:
                    if usb_device.get('board_id', '') in ['', '0000000000']:
                        self.errors = "board_id unset"
                    if usb_device.get('usb_vendor_id', '') == '0000':
                        self.errors = 'usb_vendor_id unset'
                    if usb_device.get('usb_product_id', '') == '0000':
                        self.errors = 'usb_product_id unset'
        except TypeError:
            self.errors = "Invalid parameters for %s" % self.name

    def run(self, connection, max_end_time, args=None):
        connection = super(LxcAddStaticDevices, self).run(connection, max_end_time, args)
        lxc_name = self.get_namespace_data(action='lxc-create-action', label='lxc', key='name')
        # If there is no static_info then this action should be idempotent.
        if 'static_info' not in self.job.device:
            return connection
        device_list = get_udev_devices(
            job=self.job, logger=self.logger,
            device_info=self.job.device.get('static_info'))
        for link in device_list:
            lxc_cmd = ['lxc-device', '-n', lxc_name, 'add', link]
            cmd_out = self.run_command(lxc_cmd, allow_silent=True)
            if cmd_out:
                self.logger.debug(cmd_out)
        return connection


class LxcStartAction(Action):
    """
    This action calls lxc-start to get into the system.
    """

    def __init__(self):
        super(LxcStartAction, self).__init__()
        self.name = "boot-lxc"
        self.summary = "attempt to boot"
        self.description = "boot into lxc container"
        self.sleep = 10

    def validate(self):
        super(LxcStartAction, self).validate()
        self.errors = infrastructure_error('lxc-start')

    def run(self, connection, max_end_time, args=None):
        connection = super(LxcStartAction, self).run(connection, max_end_time, args)
        lxc_name = self.get_namespace_data(action='lxc-create-action', label='lxc', key='name')
        lxc_cmd = ['lxc-start', '-n', lxc_name, '-d']
        command_output = self.run_command(lxc_cmd)
        if command_output and command_output is not '':
            raise JobError("Unable to start lxc container: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        lxc_cmd = ['lxc-info', '-sH', '-n', lxc_name]
        self.logger.debug("Wait until '%s' state becomes RUNNING", lxc_name)
        while True:
            command_output = self.run_command(lxc_cmd, allow_fail=True)
            if command_output and 'RUNNING' in command_output.strip():
                break
            time.sleep(self.sleep)  # poll every 10 seconds.
        self.logger.info("'%s' state is RUNNING", lxc_name)
        # Check if LXC got an IP address so that we are sure, networking is
        # enabled and the LXC can update or install software.
        lxc_cmd = ['lxc-info', '-iH', '-n', lxc_name]
        self.logger.debug("Wait until '%s' gets an IP address", lxc_name)
        while True:
            command_output = self.run_command(lxc_cmd, allow_fail=True)
            if command_output:
                break
            time.sleep(self.sleep)  # poll every 10 seconds.
        self.logger.info("'%s' IP address is: '%s'", lxc_name,
                         command_output.strip())
        return connection


class LxcStopAction(Action):
    """
    This action calls lxc-stop to stop the container.
    """

    def __init__(self):
        super(LxcStopAction, self).__init__()
        self.name = "lxc-stop"
        self.summary = "stop lxc"
        self.description = "stop the lxc container"

    def validate(self):
        super(LxcStopAction, self).validate()
        self.errors = infrastructure_error('lxc-stop')

    def run(self, connection, max_end_time, args=None):
        connection = super(LxcStopAction, self).run(connection, max_end_time, args)
        lxc_name = self.get_namespace_data(action='lxc-create-action',
                                           label='lxc', key='name')
        lxc_cmd = ['lxc-stop', '-k', '-n', lxc_name]
        command_output = self.run_command(lxc_cmd)
        if command_output and command_output is not '':
            raise JobError("Unable to stop lxc container: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection
