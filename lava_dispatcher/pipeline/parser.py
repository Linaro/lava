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

import copy
import yaml

from yaml.composer import Composer
from yaml.constructor import Constructor
from lava_dispatcher.pipeline import *
from lava_dispatcher.pipeline.job_actions.deploy.kvm import DeployAction, DeployKVM


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

    def parse(self, io, device, output_dir=None):
        self.loader = yaml.Loader(io)
        self.loader.compose_node = self.compose_node
        self.loader.construct_mapping = self.construct_mapping
        data = self.loader.get_single_data()

        job = Job(data)
        job.parameters['output_dir'] = output_dir
        pipeline = Pipeline(job=job)
        for action_data in data['actions']:
            line = action_data.pop('yaml_line', None)
            for name in action_data:
                if name == "deploy":
                    # allow the classmethod to check the parameters
                    d = Deployment.select(device, action_data[name])(pipeline)
                    d.action.parameters = action_data[name]  # still need to pass the parameters to the instance
                    d.action.yaml_line = line
                else:
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

        # the only parameters sent to the job are job parameters
        # like job_name, logging_level or target_group.
        data.pop('actions')
        data['output_dir'] = output_dir
        job.set_pipeline(pipeline)
        return job
