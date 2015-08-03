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
from lava_dispatcher.pipeline.job import Job, ResetContext
from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    Timeout,
)
from lava_dispatcher.pipeline.logical import (
    Deployment,
    Boot,
    LavaTest,
)
from lava_dispatcher.pipeline.deployment_data import get_deployment_data
from lava_dispatcher.pipeline.power import FinalizeAction
from lava_dispatcher.pipeline.connection import Protocol
# Bring in the strategy subclass lists, ignore pylint warnings.
# pylint: disable=unused-import
from lava_dispatcher.pipeline.actions.commands import CommandsAction
import lava_dispatcher.pipeline.actions.deploy.strategies
import lava_dispatcher.pipeline.actions.boot.strategies
import lava_dispatcher.pipeline.actions.test.strategies
import lava_dispatcher.pipeline.protocols.strategies


def parse_action(job_data, name, device, pipeline):
    """
    If protocols are defined, each Action may need to be aware of the protocol parameters.
    """
    parameters = job_data[name]
    if 'protocols' in pipeline.job.parameters:
        parameters.update(pipeline.job.parameters['protocols'])

    if name == 'boot':
        Boot.select(device, job_data[name])(pipeline, parameters)
    elif name == 'test':
        LavaTest.select(device, job_data[name])(pipeline, parameters)
    elif name == 'deploy':
        parameters.update({'deployment_data': get_deployment_data(parameters.get('os', ''))})
        Deployment.select(device, job_data[name])(pipeline, parameters)


class JobParser(object):
    """
    Creates a Job object from the Device and the job YAML by selecting the
    Strategy class with the highest priority for the parameters of the job.

    Adding new behaviour is a two step process:
     - always add a new Action, usually with an internal pipeline, to implement the new behaviour
     - add a new Strategy class which creates a suitable pipeline to use that Action.

    Re-use existing Action classes wherever these can be used without changes.

    If two or more Action classes have very similar behaviour, re-factor to make a
    new base class for the common behaviour and retain the specialised classes.

    Strategy selection via select() must only ever rely on the device and the
    job parameters. Add new parameters to the job to distinguish strategies, e.g.
    the boot method or deployment method.
    """

    # FIXME: needs a Schema and a check routine

    loader = None
    context = {}

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

    def _timeouts(self, data, job):
        if 'timeouts' in data and data['timeouts']:
            if 'job' in data['timeouts']:
                duration = Timeout.parse(data['timeouts']['job'])
                job.timeout = Timeout(data['job_name'], duration)
            if 'action' in data['timeouts']:
                self.context['default_action_duration'] = Timeout.parse(data['timeouts']['action'])
            if 'test' in data['timeouts']:
                self.context['default_test_duration'] = Timeout.parse(data['timeouts']['test'])

    # FIXME: add a validate() function which checks against a Schema as a completely separate step.
    # pylint: disable=too-many-locals,too-many-statements
    def parse(self, content, device, job_id, socket_addr, output_dir=None,
              env_dut=None):
        self.loader = yaml.Loader(content)
        self.loader.compose_node = self.compose_node
        self.loader.construct_mapping = self.construct_mapping
        data = self.loader.get_single_data()

        self.context['default_action_duration'] = Timeout.default_duration()
        self.context['default_test_duration'] = Timeout.default_duration()
        job = Job(job_id, socket_addr, data)
        counts = {}
        job.device = device
        job.parameters['output_dir'] = output_dir
        job.parameters['env_dut'] = env_dut
        job.parameters['target'] = device.target
        for instance in Protocol.select_all(job.parameters):
            job.protocols.append(instance(job.parameters))
        pipeline = Pipeline(job=job)
        self._timeouts(data, job)

        # FIXME: also read permissable overrides from device config and set from job data
        # FIXME: ensure that a timeout for deployment 0 does not get set as the timeout for deployment 1 if 1 is default
        for action_data in data['actions']:
            action_data.pop('yaml_line', None)
            for name in action_data:
                if type(action_data[name]) is dict:  # FIXME: commands are not fully implemented & may produce a list
                    action_data[name]['default_action_timeout'] = self.context['default_action_duration']
                    action_data[name]['default_test_timeout'] = self.context['default_test_duration']
                counts.setdefault(name, 1)
                if name == 'deploy' or name == 'boot' or name == 'test':
                    # reset the context before adding a second deployment and again before third etc.
                    if name == 'deploy' and counts[name] >= 2:
                        reset_context = ResetContext()
                        reset_context.section = name
                        pipeline.add_action(reset_context)
                    parse_action(action_data, name, device, pipeline)
                elif name == 'repeat':
                    count = action_data[name]['count']  # first list entry must be the count dict
                    repeats = action_data[name]['actions']
                    for c_iter in xrange(count):
                        for repeating in repeats:  # block of YAML to repeat
                            for repeat_action in repeating:  # name of the action for this block
                                if repeat_action == 'yaml_line':
                                    continue
                                repeating[repeat_action]['repeat-count'] = c_iter
                                parse_action(repeating, repeat_action, device, pipeline)

                else:
                    # May only end up being used for submit as other actions all need strategy method objects
                    # select the specific action of this class for this job
                    action = Action.select(name)()
                    action.job = job
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
                    action.timeout = Timeout(action.name, self.context['default_action_duration'])
                    pipeline.add_action(action)
                counts[name] += 1

        # there's always going to need to be a finalize_process action
        pipeline.add_action(FinalizeAction())
        data['output_dir'] = output_dir
        job.set_pipeline(pipeline)
        return job
