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

import yaml
from yaml.composer import Composer
from yaml.constructor import Constructor
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    Deployment,
    Boot,
    FinalizeAction,
    LavaTest,
    JobError
)
from lava_dispatcher import deployment_data
# needed for the Deployment select call, despite what pylint thinks.
from lava_dispatcher.pipeline.actions.deploy.image import DeployImage  # pylint: disable=unused-import
from lava_dispatcher.pipeline.actions.boot.kvm import BootKVM  # pylint: disable=unused-import


class JobParser(object):

    loader = None

    # annotate every object in data with line numbers so we can use
    # them is user-friendly validation messages, combined with the action.level
    # each action will also include an output_line to map to the stdout log,
    # once executed.

    def compose_node(self, parent, index):
        # the line number where the previous token has ended (plus empty lines)
        line = self.loader.line
        node = Composer.compose_node(self.loader, parent, index)
        node.__line__ = line + 1
        return node

    def construct_mapping(self, node, deep=False):
        mapping = Constructor.construct_mapping(self.loader, node, deep=deep)
        mapping['yaml_line'] = node.__line__
        return mapping

    def parse_check(self, content, device_config):
        # FIXME: fold into the regular parsing by handling the device_config instead of the old Device class
        if 'image' not in device_config['actions']['boot']['allow']:
            raise JobError("Unable to boot job")
        if 'image' not in device_config['actions']['deploy']['allow']:
            raise JobError("Unable to deploy job")

    def parse(self, content, device, output_dir=None):
        self.loader = yaml.Loader(content)
        self.loader.compose_node = self.compose_node
        self.loader.construct_mapping = self.construct_mapping
        data = self.loader.get_single_data()

        job = Job(data)

        job.device = device
        job.parameters['output_dir'] = output_dir
        pipeline = Pipeline(job=job)
        for action_data in data['actions']:
            line = action_data.pop('yaml_line', None)
            for name in action_data:
                if name == "deploy":
                    # allow the classmethod to check the parameters
                    deploy = Deployment.select(device, action_data[name])(pipeline)
                    deploy.action.parameters = action_data[name]  # still need to pass the parameters to the instance
                    if 'test' in data['actions']:
                        deploy.action.parameters = action_data['test']
                    deploy.action.yaml_line = line
                    device.deployment_data = deployment_data.get(deploy.action.parameters['os'])
                    deploy.action.parameters = {'deployment_data': device.deployment_data}
                elif name == "boot":
                    boot = Boot.select(device, action_data[name])(pipeline)
                    boot.action.parameters = action_data[name]
                    boot.action.yaml_line = line
#                elif name == "test":
#                    lavatest = LavaTest.select(device, action_data[name])(pipeline)
#                    lavatest.action.parameters = action_data[name]
#                    lavatest.action.yaml_line = line
                else:
                    # May only end up being used for submit as other actions all need strategy method objects
                    action_class = Action.find(name)
                    # select the specific action of this class for this job
                    action = action_class()
                    # put parameters (like rootfs_type, results_dir) into the actions.
                    if type(action_data[name]) == dict:
                        action.parameters = action_data[name]
                    elif name == "commands":
                        # FIXME
                        pass
                    elif type(action_data[name]) == list:
                        for param in action_data[name]:
                            action.parameters = param
                    action.summary = name
                    pipeline.add_action(action)
                # uncomment for debug
                # print action.parameters

        # there's always going to need to be a finalize_process action
        pipeline.add_action(FinalizeAction())
        # the only parameters sent to the job are job parameters
        # like job_name, logging_level or target_group.
        data.pop('actions')
        data['output_dir'] = output_dir
        job.set_pipeline(pipeline)
        return job
