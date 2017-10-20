# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
)
from lava_dispatcher.pipeline.logical import Boot, RetryAction
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.shell import (
    ExpectShellSession,
    ShellCommand,
    ShellSession
)


class BootDocker(Boot):
    compatibility = 4

    def __init__(self, parent, parameters):
        super(BootDocker, self).__init__(parent)
        self.action = BootDockerAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if "docker" not in device['actions']['boot']['methods']:
            return False, '"docker" was not in the device configuration boot methods'
        if "command" not in parameters:
            return False, '"command" was not in boot parameters'
        return True, 'accepted'


class BootDockerAction(BootAction):

    def __init__(self):
        super(BootDockerAction, self).__init__()
        self.name = 'boot-docker'
        self.description = "boot docker image"
        self.summary = "boot docker image"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootDockerRetry())
        if self.has_prompts(parameters):
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())


class BootDockerRetry(RetryAction):

    def __init__(self):
        super(BootDockerRetry, self).__init__()
        self.name = 'boot-docker-retry'
        self.description = "boot docker image with retry"
        self.summary = "boot docker image"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(CallDockerAction())


class CallDockerAction(Action):

    def __init__(self):
        super(CallDockerAction, self).__init__()
        self.name = "docker-run"
        self.description = "call docker run on the image"
        self.summary = "call docker run"
        self.cleanup_required = False
        self.extra_options = ''

    def validate(self):
        super(CallDockerAction, self).validate()
        self.container = "lava-%s-%s" % (self.job.job_id, self.level)

        options = self.job.device['actions']['boot']['methods']['docker']['options']

        if options['cpus']:
            self.extra_options += ' --cpus %s' % options['cpus']
        if options['memory']:
            self.extra_options += ' --memory %s' % options['memory']
        if options['volumes']:
            for volume in options['volumes']:
                self.extra_options += ' --volume %s' % volume

    def run(self, connection, max_end_time, args=None):
        location = self.get_namespace_data(action='test', label='shared', key='location')
        overlay = self.get_namespace_data(action='test', label='results', key='lava_test_results_dir')
        docker_image = self.get_namespace_data(action='deploy-docker', label='image', key='name')

        # Build the command line
        # The docker image is safe to be included in the command line
        cmd = "docker run --interactive --tty --hostname lava"
        cmd += " --name %s" % self.container
        cmd += " --volume %s:%s" % (os.path.join(location, overlay.strip("/")), overlay)
        cmd += self.extra_options
        cmd += " %s %s" % (docker_image, self.parameters["command"])

        self.logger.debug("Boot command: %s", cmd)
        shell = ShellCommand(cmd, self.timeout, logger=self.logger)
        self.cleanup_required = True

        shell_connection = ShellSession(self.job, shell)
        shell_connection = super(CallDockerAction, self).run(shell_connection, max_end_time, args)

        self.set_namespace_data(action='shared', label='shared', key='connection', value=shell_connection)
        return shell_connection

    def cleanup(self, connection):
        super(CallDockerAction, self).cleanup(connection)
        if self.cleanup_required:
            self.logger.debug("Stopping container %s", self.container)
            self.run_command(["docker", "stop", self.container], allow_fail=True)
            self.logger.debug("Removing container %s", self.container)
            self.run_command(["docker", "rm", self.container], allow_fail=True)
            self.cleanup_required = False
