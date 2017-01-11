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
    Timeout,
    JobError,
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
# pylint: disable=unused-import,too-many-arguments,too-many-nested-blocks,too-many-branches
from lava_dispatcher.pipeline.actions.commands import CommandsAction
import lava_dispatcher.pipeline.actions.deploy.strategies
import lava_dispatcher.pipeline.actions.boot.strategies
import lava_dispatcher.pipeline.actions.test.strategies
import lava_dispatcher.pipeline.protocols.strategies


def parse_action(job_data, name, device, pipeline, test_info, count):
    """
    If protocols are defined, each Action may need to be aware of the protocol parameters.
    """
    parameters = job_data[name]
    parameters.update({'namespace': parameters.get('namespace', 'common')})
    parameters.update({'test_info': test_info})
    if 'protocols' in pipeline.job.parameters:
        parameters.update(pipeline.job.parameters['protocols'])

    if name == 'boot':
        Boot.select(device, parameters)(pipeline, parameters)
    elif name == 'test':
        # stage starts at 0
        parameters['stage'] = count - 1
        LavaTest.select(device, parameters)(pipeline, parameters)
    elif name == 'deploy':
        if parameters['namespace'] in test_info:
            if any([testclass for testclass in test_info[parameters['namespace']] if testclass['class'].needs_deployment_data()]):
                parameters.update({'deployment_data': get_deployment_data(parameters.get('os', ''))})
        if 'preseed' in parameters:
            parameters.update({'deployment_data': get_deployment_data(parameters.get('os', ''))})
        Deployment.select(device, parameters)(pipeline, parameters)


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
            if 'connection' in data['timeouts']:
                self.context['default_connection_duration'] = Timeout.parse(data['timeouts']['connection'])
            if 'test' in data['timeouts']:
                self.context['default_test_duration'] = Timeout.parse(data['timeouts']['test'])

    def _map_context_defaults(self):
        return {
            'default_action_timeout': self.context['default_action_duration'],
            'default_test_timeout': self.context['default_test_duration'],
            'default_connection_timeout': self.context['default_connection_duration']
        }

    # pylint: disable=too-many-locals,too-many-statements
    def parse(self, content, device, job_id, zmq_config, dispatcher_config,
              output_dir=None, env_dut=None):
        self.loader = yaml.Loader(content)
        self.loader.compose_node = self.compose_node
        self.loader.construct_mapping = self.construct_mapping
        data = self.loader.get_single_data()
        self.context['default_action_duration'] = Timeout.default_duration()
        self.context['default_test_duration'] = Timeout.default_duration()
        self.context['default_connection_duration'] = Timeout.default_duration()
        job = Job(job_id, data, zmq_config)
        counts = {}
        job.device = device
        job.parameters['output_dir'] = output_dir
        job.parameters['env_dut'] = env_dut
        job.parameters['target'] = device.target
        # Load the dispatcher config
        job.parameters['dispatcher'] = {}
        if dispatcher_config is not None:
            job.parameters['dispatcher'] = yaml.load(dispatcher_config)

        # Setup the logging now that we have the parameters
        job.setup_logging()

        level_tuple = Protocol.select_all(job.parameters)
        # sort the list of protocol objects by the protocol class level.
        job.protocols = [item[0](job.parameters, job_id) for item in sorted(level_tuple, key=lambda level_tuple: level_tuple[1])]
        pipeline = Pipeline(job=job)
        self._timeouts(data, job)

        # deploy and boot classes can populate the pipeline differently depending
        # on the test action type they are linked with (via namespacing).
        # This code builds an information dict for each namespace which is then
        # passed as a parameter to each Action class to use.
        test_info = {}
        test_actions = ([action for action in data['actions'] if 'test' in action])
        for test_action in test_actions:
            test_parameters = test_action['test']
            test_type = LavaTest.select(device, test_parameters)
            namespace = test_parameters.get('namespace', 'common')
            if namespace in test_info:
                test_info[namespace].append({'class': test_type, 'parameters': test_parameters})
            else:
                test_info.update({namespace: [{'class': test_type, 'parameters': test_parameters}]})

        # FIXME: also read permissable overrides from device config and set from job data
        # FIXME: ensure that a timeout for deployment 0 does not get set as the timeout for deployment 1 if 1 is default
        for action_data in data['actions']:
            action_data.pop('yaml_line', None)
            for name in action_data:
                if isinstance(action_data[name], dict):  # FIXME: commands are not fully implemented & may produce a list
                    action_data[name].update(self._map_context_defaults())
                counts.setdefault(name, 1)
                if name == 'deploy' or name == 'boot' or name == 'test':
                    parse_action(action_data, name, device, pipeline,
                                 test_info, counts[name])
                elif name == 'repeat':
                    count = action_data[name]['count']  # first list entry must be the count dict
                    repeats = action_data[name]['actions']
                    for c_iter in range(count):
                        for repeating in repeats:  # block of YAML to repeat
                            for repeat_action in repeating:  # name of the action for this block
                                if repeat_action == 'yaml_line':
                                    continue
                                repeating[repeat_action]['repeat-count'] = c_iter
                                parse_action(repeating, repeat_action, device,
                                             pipeline, test_info, counts[name])

                else:
                    # May only end up being used for submit as other actions all need strategy method objects
                    # select the specific action of this class for this job
                    action = Action.select(name)()
                    action.job = job
                    # put parameters (like rootfs_type, results_dir) into the actions.
                    if isinstance(action_data[name], dict):
                        action.parameters = action_data[name]
                    elif name == "commands":
                        # FIXME
                        pass
                    elif isinstance(action_data[name], list):
                        for param in action_data[name]:
                            action.parameters = param
                    action.summary = name
                    action.timeout = Timeout(action.name, self.context['default_action_duration'])
                    action.connection_timeout = Timeout(action.name, self.context['default_connection_duration'])
                    pipeline.add_action(action)
                counts[name] += 1

        # there's always going to need to be a finalize_process action
        finalize = FinalizeAction()
        pipeline.add_action(finalize)
        finalize.populate(self._map_context_defaults())
        data['output_dir'] = output_dir
        job.pipeline = pipeline
        if 'compatibility' in data:
            try:
                job_c = int(job.compatibility)
                data_c = int(data['compatibility'])
            except ValueError as exc:
                raise JobError('invalid compatibility value: %s' % exc)
            if job_c < data_c:
                raise JobError('Dispatcher unable to meet job compatibility requirement. %d > %d' % (job_c, data_c))
        return job
