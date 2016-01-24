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


import os
import tarfile
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
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction
from lava_dispatcher.pipeline.connections.lxc import (
    ConnectLxc,
)
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.constants import (
    LXC_PATH,
)


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
                return True
        return False


class BootLxcAction(BootAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the
    connection after boot.
    """
    def __init__(self):
        super(BootLxcAction, self).__init__()
        self.name = "lxc_boot"
        self.summary = "lxc boot"
        self.description = "lxc boot into the system"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(LxcStartAction())
        self.internal_pipeline.add_action(ConnectLxc())
        # Add AutoLoginAction unconditionnally as this action does nothing if
        # the configuration does not contain 'auto_login'
        self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(ExportDeviceEnvironment())
        self.internal_pipeline.add_action(LxcOverlayUnpack())


class LxcStartAction(Action):
    """
    This action calls lxc-start to get into the system.
    """

    def __init__(self):
        super(LxcStartAction, self).__init__()
        self.name = "boot-lxc"
        self.summary = "attempt to boot"
        self.description = "boot into lxc container"
        self.command = ''

    def validate(self):
        super(LxcStartAction, self).validate()
        self.errors = infrastructure_error('lxc-start')

    def run(self, connection, args=None):
        connection = super(LxcStartAction, self).run(connection, args)
        lxc_cmd = ['lxc-start', '-n', self.get_common_data('lxc', 'name'),
                   '-d']
        command_output = self.run_command(lxc_cmd)
        if command_output and command_output is not '':
            raise JobError("Unable to start lxc container: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection


class LxcOverlayUnpack(Action):

    def __init__(self):
        super(LxcOverlayUnpack, self).__init__()
        self.name = "lxc-overlay-unpack"
        self.summary = "unpack the overlay on the container"
        self.description = "unpack the overlay to the container by copying"

    def validate(self):
        super(LxcOverlayUnpack, self).validate()
        self.errors = infrastructure_error('tar')

    def run(self, connection, args=None):
        connection = super(LxcOverlayUnpack, self).run(connection, args)
        overlay_file = self.data['compress-overlay'].get('output')
        lxc_path = os.path.join(LXC_PATH, self.get_common_data('lxc', 'name'),
                                "rootfs")
        if not os.path.exists(lxc_path):
            raise JobError("Lxc container rootfs not found")
        tar_cmd = ['tar', '--warning', 'no-timestamp', '-C', lxc_path, '-xaf',
                   overlay_file]
        command_output = self.run_command(tar_cmd)
        if command_output and command_output is not '':
            raise JobError("Unable to untar overlay: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return connection
