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


from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    JobError,
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.deploy.lxc import LxcAddDeviceAction


class BootFastboot(Boot):
    """
    Expects fastboot bootloader, and boots.
    """
    compatibility = 1

    def __init__(self, parent, parameters):
        super(BootFastboot, self).__init__(parent)
        self.action = BootFastbootAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' in parameters:
            if parameters['method'] == 'fastboot':
                return True
        return False


class BootFastbootAction(BootAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the
    connection after boot.
    """
    def __init__(self):
        super(BootFastbootAction, self).__init__()
        self.name = "fastboot_boot"
        self.summary = "fastboot boot"
        self.description = "fastboot boot into the system"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(FastbootBootAction())
        self.internal_pipeline.add_action(LxcAddDeviceAction())


class FastbootBootAction(Action):
    """
    This action calls fastboot to boot into the system.
    """

    def __init__(self):
        super(FastbootBootAction, self).__init__()
        self.name = "boot-fastboot"
        self.summary = "attempt to fastboot boot"
        self.description = "fastboot boot into system"

    def validate(self):
        super(FastbootBootAction, self).validate()
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(FastbootBootAction, self).run(connection, args)
        lxc_name = self.get_namespace_data(
            action='lxc-create-action',
            label='lxc',
            key='name'
        )
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'reboot']
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'rebooting' not in command_output:
            raise JobError("Unable to boot with fastboot: %s" % command_output)
        else:
            status = [status.strip() for status in command_output.split(
                '\n') if 'finished' in status][0]
            self.results = {'status': status}
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        return connection
