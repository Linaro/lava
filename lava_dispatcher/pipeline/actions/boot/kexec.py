# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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
    Timeout
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction


class BootKExec(Boot):
    """
    Expects a shell session, checks for kexec executable and
    prepares the arguments to run kexec,
    """
    def __init__(self, parent, parameters):
        super(BootKExec, self).__init__(parent)
        self.action = BootKexecAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' in parameters:
            if parameters['method'] == 'kexec':
                return True
        return False


class BootKexecAction(BootAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the connection after boot
    """
    def __init__(self):
        super(BootKexecAction, self).__init__()
        self.name = "kexec_boot"
        self.summary = "kexec a new kernel"
        self.description = "replace current kernel using kexec"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(KexecAction())
        # Add AutoLoginAction unconditionnally as this action does nothing if
        # the configuration does not contain 'auto_login'
        self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(ExportDeviceEnvironment())


class KexecAction(Action):
    """
    The files need to have been downloaded by a previous test action.
    This action calls kexec to load the kernel ,execute it and then
    attempts to reestablish the shell connection after boot.
    """

    def __init__(self):
        super(KexecAction, self).__init__()
        self.name = "call-kexec"
        self.summary = "attempt to kexec new kernel"
        self.description = "call kexec with specified arguments"
        self.command = ''

    def validate(self):
        super(KexecAction, self).validate()
        self.command = self.parameters.get('command', '/sbin/kexec')
        self.load_command = self.command[:]  # local copy for idempotency
        self.command += ' -e'
        if 'kernel' in self.parameters:
            self.load_command += ' --load %s' % self.parameters['kernel']
        if 'dtb' in self.parameters:
            self.load_command += ' --dtb %s' % self.parameters['dtb']
        if 'initrd' in self.parameters:
            self.load_command += ' --initrd %s' % self.parameters['initrd']
        if 'options' in self.parameters:
            for option in self.parameters['options']:
                self.load_command += " %s" % option
        if self.load_command == '/sbin/kexec':
            self.errors = "Default kexec handler needs at least a kernel to pass to the --load command"

    def run(self, connection, args=None):
        """
        If kexec fails, there is no real chance at diagnostics because the device will be hung.
        Get the output prior to the call, in case this helps after the job fails.
        """
        connection = super(KexecAction, self).run(connection, args)
        if 'kernel-config' in self.parameters:
            cmd = "zgrep -i kexec %s |grep -v '^#'" % self.parameters['kernel-config']
            self.logger.debug("Checking for kexec: %s" % cmd)
            connection.sendline(cmd)
        connection.sendline(self.load_command)
        self.wait(connection)
        connection.prompt = self.parameters['boot_message']
        connection.sendline(self.command)
        return connection
