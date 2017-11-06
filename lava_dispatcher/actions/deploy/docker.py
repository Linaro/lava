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

import re
import subprocess

from lava_dispatcher.action import JobError, Pipeline
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.utils.shell import infrastructure_error


class DockerAction(DeployAction):

    def __init__(self):
        super(DockerAction, self).__init__()
        self.name = "deploy-docker"
        self.description = "deploy docker images"
        self.summary = "deploy docker"

    def validate(self):
        super(DockerAction, self).validate()
        err = infrastructure_error("docker")
        if err is not None:
            self.errors = err
            return

        # Print docker version
        out = subprocess.check_output(["docker", "version", "-f", "{{.Server.Version}}"])
        out = out.strip("\n").decode("utf-8")
        self.logger.debug("docker server, installed at version: %s", out)
        out = subprocess.check_output(["docker", "version", "-f", "{{.Client.Version}}"])
        out = out.strip("\n").decode("utf-8")
        self.logger.debug("docker client, installed at version: %s", out)

        # Add the lava_test_results_dir to the right namespace
        if self.test_needs_deployment(self.parameters):
            lava_test_results_dir = self.parameters['deployment_data'][
                'lava_test_results_dir']
            lava_test_results_dir = lava_test_results_dir % self.job.job_id
            self.set_namespace_data(action='test', label='results',
                                    key='lava_test_results_dir',
                                    value=lava_test_results_dir)
            lava_test_sh_cmd = self.parameters['deployment_data'][
                'lava_test_sh_cmd']
            self.set_namespace_data(action=self.name, label='shared',
                                    key='lava_test_sh_cmd',
                                    value=lava_test_sh_cmd)

        # check docker image name
        # The string should be safe for command line inclusion
        image_name = self.parameters["image"]
        if re.compile("^[a-z0-9._:/-]+$").match(image_name) is None:
            self.errors = "image_name '%s' is invalid" % image_name
        self.set_namespace_data(action=self.name, label='image',
                                key='name', value=image_name)

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_deployment(parameters):
            self.internal_pipeline.add_action(DeployDeviceEnvironment())
        if self.test_needs_overlay(parameters):
            self.internal_pipeline.add_action(OverlayAction())

    def run(self, connection, max_end_time, args=None):
        # Pull the image
        cmd = ["docker", "pull", self.parameters["image"]]
        out = self.run_command(cmd, allow_fail=False, allow_silent=False)
        if not out:
            msg = "Unable to pull docker image '%s'" % self.parameters["image"]
            raise JobError(msg)

        return super(DockerAction, self).run(connection, max_end_time, args)


class Docker(Deployment):
    compatibility = 4
    name = 'docker'

    def __init__(self, parent, parameters):
        super(Docker, self).__init__(parent)
        self.action = DockerAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'docker' not in device['actions']['deploy']['methods']:
            return False, "'docker' not in the device configuration deploy methods"
        if parameters['to'] != 'docker':
            return False, '"to" parameter is not "docker"'
        if 'image' not in parameters:
            return False, '"image" is not in the deployment parameters'
        return True, 'accepted'
