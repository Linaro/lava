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
from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    JobError,
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.boot.environment import (
    ExportDeviceEnvironment,
)
from lava_dispatcher.pipeline.connections.lxc import (
    ConnectLxc,
)
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.utils.shell import infrastructure_error


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
        self.internal_pipeline.add_action(ConnectLxc())
        # Skip AutoLoginAction unconditionally as this action tries to parse kernel message
        # self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(ExportDeviceEnvironment())


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
        lxc_cmd = ['lxc-attach', '-n', lxc_name, 'runlevel']
        self.logger.debug("Waiting for '%s' to become ready", lxc_name)
        while True:
            command_output = self.run_command(lxc_cmd, allow_fail=True)
            if command_output and command_output not in ['unknown', 'S']:
                break
            time.sleep(self.sleep)  # poll every 10 seconds.
        self.logger.info("'%s' is ready", lxc_name)
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
