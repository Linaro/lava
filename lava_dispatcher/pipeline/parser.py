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
    Deployment,
    Boot,
    LavaTest,
    Timeout,
)
from lava_dispatcher.pipeline.actions.commands import CommandsAction  # pylint: disable=unused-import
from lava_dispatcher.pipeline.deployment_data import get_deployment_data
from lava_dispatcher.pipeline.power import FinalizeAction
# Bring in the strategy subclass lists, ignore pylint warnings.
import lava_dispatcher.pipeline.actions.deploy.strategies  # pylint: disable=unused-import
import lava_dispatcher.pipeline.actions.boot.strategies  # pylint: disable=unused-import
import lava_dispatcher.pipeline.actions.test.strategies  # pylint: disable=unused-import
from lava_dispatcher.pipeline.actions.submit import SubmitResultsAction  # pylint: disable=unused-import


def handle_device_parameters(job_data, name, parameters):
    """
    Parses the action specific parameters from the device configuration
    to be added to the matching action parameters.
    name refers to the action name in the YAML.
    Some methods have parameters, some do not.
    Returns a dict of the device parameters for the method
    """
    retval = {}
    if 'actions' not in parameters:
        return retval
    if name not in parameters['actions']:
        return retval
    if 'method' in job_data and 'methods' in parameters['actions'][name]:
        # distinguish between methods with and without parameters in the YAML
        if job_data['method'] in parameters['actions'][name]['methods']:
            retval[job_data['method']] = [
                method for method in parameters['actions'][name]['methods'] if job_data['method'] in method
            ][0]
        elif type(parameters['actions'][name]['methods'] == list):
            retval = [
                method for method in parameters['actions'][name]['methods'] if job_data['method'] in method
            ][0]
            # print retval
        else:
            raise RuntimeError("no method parameters for %s %s" % (name, job_data['method']))
    elif 'to' in job_data and 'methods' in parameters['actions'][name]:
        # FIXME: rationalise the use of deploy methods to match job data against device data, as with boot
        retval = parameters['actions'][name]
    else:
        raise RuntimeError("Specified method does not match device methods for %s" % name)
    return retval


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
        if 'timeouts' in data:
            if 'job' in data['timeouts']:
                duration = Timeout.parse(data['timeouts']['job'])
                job.timeout = Timeout(data['job_name'], duration)
            if 'action' in data['timeouts']:
                self.context['default_action_duration'] = Timeout.parse(data['timeouts']['action'])
            if 'test' in data['timeouts']:
                self.context['default_test_duration'] = Timeout.parse(data['timeouts']['test'])
            skip_set = {'job', 'action', 'yaml_line', 'test'}
            for override in list(set(data['timeouts'].keys()) - skip_set):
                job.overrides['timeouts'][override] = Timeout.parse(data['timeouts'][override])

    # FIXME: add a validate() function which checks against a Schema as a completely separate step.
    def parse(self, content, device, output_dir=None):  # pylint: disable=too-many-locals
        self.loader = yaml.Loader(content)
        self.loader.compose_node = self.compose_node
        self.loader.construct_mapping = self.construct_mapping
        data = self.loader.get_single_data()

        self.context['default_action_duration'] = Timeout.default_duration()
        self.context['default_test_duration'] = Timeout.default_duration()
        job = Job(data)
        counts = {}
        job.device = device
        job.overrides.update(device.overrides)
        job.parameters['output_dir'] = output_dir
        pipeline = Pipeline(job=job)
        self._timeouts(data, job)

        # FIXME: also read permissable overrides from device config and set from job data
        for action_data in data['actions']:
            line = action_data.pop('yaml_line', None)
            for name in action_data:
                if type(action_data[name]) is dict:  # FIXME: commands are not fully implemented & may produce a list
                    action_data[name]['default_action_timeout'] = self.context['default_action_duration']
                    action_data[name]['default_test_timeout'] = self.context['default_test_duration']
                counts.setdefault(name, 1)
                if name == "deploy":
                    # reset the context before adding a second deployment and again before third etc.
                    if counts[name] >= 2:
                        pipeline.add_action(ResetContext())
                    # set parameters specified in the device configuration, allow job to override.
                    parameters = handle_device_parameters(action_data[name], name, device.parameters)
                    parameters.update(action_data[name])  # pass the job parameters to the instance
                    parameters['deployment_data'] = get_deployment_data(parameters.get('os', ''))
                    # allow the classmethod to check the parameters
                    deploy = Deployment.select(device, action_data[name])(pipeline, parameters)
                    deploy.action.yaml_line = line
                elif name == "boot":
                    parameters = handle_device_parameters(action_data[name], name, device.parameters)
                    parameters.update(action_data[name])
                    boot = Boot.select(device, action_data[name])(pipeline, parameters)
                    boot.action.yaml_line = line
                elif name == "test":
                    # allow for multiple base tests, e.g. Android
                    parameters = handle_device_parameters(action_data[name], name, device.parameters)
                    parameters.update(action_data[name])
                    LavaTest.select(device, action_data[name])(pipeline, parameters)
                else:
                    # May only end up being used for submit as other actions all need strategy method objects
                    # select the specific action of this class for this job
                    action = Action.find(name)()
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
                # uncomment for debug
                # print action.parameters

        # there's always going to need to be a finalize_process action
        pipeline.add_action(FinalizeAction())
        data['output_dir'] = output_dir
        job.set_pipeline(pipeline)
        return job
