# Copyright (C) 2014-2019 Linaro Limited
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

# Bring in the strategy subclass lists, ignore pylint warnings.
# pylint: disable=unused-import
import lava_dispatcher.actions.boot.strategies
import lava_dispatcher.actions.deploy.strategies
import lava_dispatcher.actions.test.strategies
import lava_dispatcher.protocols.strategies
from lava_common.compat import yaml_safe_load
from lava_dispatcher.action import JobError, Pipeline, Timeout
from lava_dispatcher.actions.commands import CommandAction
from lava_dispatcher.connection import Protocol
from lava_dispatcher.deployment_data import get_deployment_data
from lava_dispatcher.job import Job
from lava_dispatcher.logical import Boot, Deployment, LavaTest
from lava_dispatcher.power import FinalizeAction


def parse_action(job_data, name, device, pipeline, test_info, test_count):
    """
    If protocols are defined, each Action may need to be aware of the protocol parameters.
    """
    parameters = job_data[name]
    if "protocols" in pipeline.job.parameters:
        parameters.update(pipeline.job.parameters["protocols"])

    if name == "boot":
        cls = Boot.select(device, parameters)
        action = cls.action()
    elif name == "test":
        parameters["stage"] = test_count
        cls = LavaTest.select(device, parameters)
        action = cls.action(parameters)
    elif name == "deploy":
        cls = Deployment.select(device, parameters)
        ns = parameters["namespace"]
        # Does the action needs deployment_data field?
        needs_deployment_data = False
        if ns in test_info and cls.uses_deployment_data():
            needs_deployment_data = any(
                [
                    t["class"].needs_deployment_data(t["parameters"])
                    for t in test_info[ns]
                ]
            )
        if needs_deployment_data or "preseed" in parameters:
            parameters.update(
                {"deployment_data": get_deployment_data(parameters.get("os", ""))}
            )
        cls = Deployment.select(device, parameters)
        action = cls.action()

    action.section = cls.section
    pipeline.add_action(action, parameters)
    pipeline.job.compatibility = max(cls.compatibility, pipeline.job.compatibility)
    return cls


class JobParser:
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

    def _timeouts(self, data, job):
        if "job" in data.get("timeouts", {}):
            duration = Timeout.parse(data["timeouts"]["job"])
            job.timeout = Timeout("job", duration)

    def parse(self, content, device, job_id, logger, dispatcher_config, env_dut=None):
        data = yaml_safe_load(content)
        job = Job(job_id, data, logger)
        test_counts = {}
        job.device = device
        job.parameters["env_dut"] = env_dut
        # Load the dispatcher config
        job.parameters["dispatcher"] = {}
        if dispatcher_config is not None:
            config = yaml_safe_load(dispatcher_config)
            if isinstance(config, dict):
                job.parameters["dispatcher"] = config

        level_tuple = Protocol.select_all(job.parameters)
        # sort the list of protocol objects by the protocol class level.
        job.protocols = [
            item[0](job.parameters, job_id)
            for item in sorted(level_tuple, key=lambda level_tuple: level_tuple[1])
        ]
        pipeline = Pipeline(job=job)
        self._timeouts(data, job)

        # deploy and boot classes can populate the pipeline differently depending
        # on the test action type they are linked with (via namespacing).
        # This code builds an information dict for each namespace which is then
        # passed as a parameter to each Action class to use.
        test_actions = [action for action in data["actions"] if "test" in action]
        for test_action in test_actions:
            test_parameters = test_action["test"]
            test_type = LavaTest.select(device, test_parameters)
            namespace = test_parameters.get("namespace", "common")
            connection_namespace = test_parameters.get(
                "connection-namespace", namespace
            )
            job.test_info.setdefault(namespace, [])
            job.test_info.setdefault(connection_namespace, [])
            job.test_info[namespace].append(
                {"class": test_type, "parameters": test_parameters}
            )
            if namespace != connection_namespace:
                job.test_info[connection_namespace].append(
                    {"class": test_type, "parameters": test_parameters}
                )

        # FIXME: also read permissible overrides from device config and set from job data
        # FIXME: ensure that a timeout for deployment 0 does not get set as the timeout for deployment 1 if 1 is default
        for action_data in data["actions"]:
            for name in action_data:
                # Set a default namespace if needed
                namespace = action_data[name].setdefault("namespace", "common")
                test_counts.setdefault(namespace, 0)

                if name in ["deploy", "boot", "test"]:
                    action = parse_action(
                        action_data,
                        name,
                        device,
                        pipeline,
                        job.test_info,
                        test_counts[namespace],
                    )
                    if name == "test" and action.needs_overlay(action_data["test"]):
                        test_counts[namespace] += 1
                elif name == "command":
                    action = CommandAction()
                    action.parameters = action_data[name]
                    pipeline.add_action(action)

                else:
                    raise JobError("Unknown action name '%s'" % name)

        # there's always going to need to be a finalize_process action
        finalize = FinalizeAction()
        pipeline.add_action(finalize)
        finalize.populate(None)
        job.pipeline = pipeline
        if "compatibility" in data:
            try:
                job_c = int(job.compatibility)
                data_c = int(data["compatibility"])
            except ValueError as exc:
                raise JobError("invalid compatibility value: %s" % exc)
            if job_c < data_c:
                raise JobError(
                    "Dispatcher unable to meet job compatibility requirement. %d > %d"
                    % (job_c, data_c)
                )
        return job
