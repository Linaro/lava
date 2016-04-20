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
    Timeout,
    JobError,
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.boot.environment import (
    ExportDeviceEnvironment,
)
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction
from lava_dispatcher.pipeline.connections.adb import (
    ConnectAdb,
    WaitForAdbDevice,
)
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.utils.constants import (
    DISPATCHER_DOWNLOAD_DIR,
    ANDROID_TMP_DIR,
)


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
        self.internal_pipeline.add_action(FastbootAction())
        self.internal_pipeline.add_action(WaitForAdbDevice())
        self.internal_pipeline.add_action(ConnectAdb())
        # Add AutoLoginAction unconditionally as this action does nothing if
        # the configuration does not contain 'auto_login'
        self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(AdbOverlayUnpack())


class FastbootAction(Action):
    """
    This action calls fastboot to reboot into the system.
    """

    def __init__(self):
        super(FastbootAction, self).__init__()
        self.name = "boot-fastboot"
        self.summary = "attempt to fastboot boot"
        self.description = "fastboot boot into system"
        self.command = ''

    def validate(self):
        super(FastbootAction, self).validate()
        self.errors = infrastructure_error('fastboot')
        if infrastructure_error('fastboot'):
            self.errors = "Unable to find 'fastboot' command"
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(FastbootAction, self).run(connection, args)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['fastboot', '-s', serial_number, 'reboot']
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'rebooting' not in command_output:
            raise JobError("Unable to boot with fastboot: %s" %
                           command_output)
        return connection


class AdbOverlayUnpack(Action):

    def __init__(self):
        super(AdbOverlayUnpack, self).__init__()
        self.name = "adb-overlay-unpack"
        self.summary = "unpack the overlay on the remote device"
        self.description = "unpack the overlay over adb"

    def validate(self):
        super(AdbOverlayUnpack, self).validate()
        if 'adb_serial_number' not in self.job.device:
            self.errors = "device adb serial number missing"
            if self.job.device['adb_serial_number'] == '0000000000':
                self.errors = "device adb serial number unset"
        if infrastructure_error('adb'):
            self.errors = "Unable to find 'adb' command"

    def run(self, connection, args=None):
        connection = super(AdbOverlayUnpack, self).run(connection, args)
        serial_number = self.job.device['adb_serial_number']
        overlay_type = 'adb-overlay'
        overlay_file = self.data['compress-overlay'].get('output')
        host_dir = mkdtemp()
        target_dir = ANDROID_TMP_DIR
        try:
            tar = tarfile.open(overlay_file)
            tar.extractall(host_dir)
            tar.close()
        except tarfile.TarError as exc:
            raise RuntimeError("Unable to unpack %s overlay: %s" % (
                overlay_type, exc))
        host_dir = os.path.join(host_dir, 'data/local/tmp')
        adb_cmd = ['adb', '-s', serial_number, 'push', host_dir,
                   target_dir]
        command_output = self.run_command(adb_cmd)
        if command_output and 'pushed' not in command_output:
            raise JobError("Unable to push overlay files with adb: %s" %
                           command_output)
        adb_cmd = ['adb', '-s', serial_number, 'shell', '/system/bin/chmod',
                   '0777', target_dir]
        command_output = self.run_command(adb_cmd)
        if command_output and 'pushed' not in command_output:
            raise JobError("Unable to chmod overlay files with adb: %s" %
                           command_output)
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return connection
