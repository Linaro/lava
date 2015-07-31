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

import logging
import yaml

from lava_dispatcher.pipeline.action import Action, JobError
from lava_dispatcher.pipeline.log import YAMLLogger  # pylint: disable=unused-import
from lava_dispatcher.pipeline.logical import PipelineContext
from lava_dispatcher.pipeline.diagnostics import DiagnoseNetwork
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol  # pylint: disable=unused-import


class Job(object):  # pylint: disable=too-many-instance-attributes
    """
    Populated by the parser, the Job contains all of the
    Actions and their pipelines.
    parameters provides the immutable data about this job:
        action_timeout
        job_name
        priority
        device_type (mapped to target by scheduler)
        yaml_line
        logging_level
        job_timeout
    Job also provides the primary access to the Device.
    The NewDevice class only loads the specific configuration of the
    device for this job - one job, one device.
    """

    def __init__(self, job_id, socket_addr, parameters):
        self.job_id = job_id
        self.socket_addr = socket_addr
        self.device = None
        self.parameters = parameters
        self.__context__ = PipelineContext()
        self.pipeline = None
        self.actions = None
        self.connection = None
        self.triggers = []  # actions can add trigger strings to the run a diagnostic
        self.diagnostics = [
            DiagnoseNetwork,
        ]
        self.timeout = None
        self.protocols = []
        # TODO: we are now able to create the logger when the job is started,
        # allowing the functions that are called before run() to log.
        # Do we want to do something with this?
        # Taking into account that the validate() function will be called on
        # the LAVA server when the job is submitted.
        # For the moment, we create the logger without the ZMQ handler that
        # will be added when running the job.
        self.logger = logging.getLogger('dispatcher')

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        self.actions = pipeline.children

    @property
    def context(self):
        return self.__context__.pipeline_data

    @context.setter
    def context(self, data):
        self.__context__.pipeline_data.update(data)

    def reset_context(self):
        """
        Called within multiple deployment jobs from an Action.run()
        """
        self.__context__ = PipelineContext()

    def diagnose(self, trigger):
        """
        Looks up the class to execute to diagnose the problem described by the
         specified trigger.
        """
        trigger_tuples = [(cls.trigger(), cls) for cls in self.diagnostics]
        for diagnostic in trigger_tuples:
            if trigger is diagnostic[0]:
                return diagnostic[1]()
        return None

    def describe(self):
        return {'device': self.device,
                'job': self.parameters,
                'pipeline': self.pipeline.describe()}

    def validate(self, simulate=False):
        """
        Needs to validate the parameters
        Then needs to validate the context
        Finally expose the context so that actions can see it.
        """
        if simulate:
            # output the content and then any validation errors (python3 compatible)
            print(yaml.dump(self.describe()))  # pylint: disable=superfluous-parens
        # FIXME: validate the device config
        # FIXME: pretty output of exception messages needed.
        self.pipeline.validate_actions()

    def run(self):
        """
        Top level routine for the entire life of the Job, using the job level timeout.
        Python only supports one alarm on SIGALRM - any Action without a connection
        will have a default timeout which will use SIGALRM. So the overarching Job timeout
        can only stop processing actions if the job wide timeout is exceeded.
        """
        # Add the ZMQ handler now
        if self.socket_addr is not None:
            self.logger.addZMQHandler(self.socket_addr, self.job_id)  # pylint: disable=maybe-no-member
        else:
            self.logger.addHandler(logging.StreamHandler())

        for protocol in self.protocols:
            try:
                protocol.set_up()
            except KeyboardInterrupt:
                self.pipeline.cleanup_actions(connection=None, message="Canceled")
                self.logger.info("Canceled")
                return 1  # equivalent to len(self.pipeline.errors)
            except (JobError, RuntimeError, KeyError, TypeError) as exc:
                raise JobError(exc)
            if not protocol.valid:
                msg = "protocol %s has errors: %s" % (protocol.name, protocol.errors)
                self.logger.exception(msg)
                raise JobError(msg)

        self.pipeline.run_actions(self.connection)
        if self.pipeline.errors:
            self.logger.exception(self.pipeline.errors)
            return len(self.pipeline.errors)
        return 0


class ResetContext(Action):
    """
    Allow multiple deployment jobs to clear the context before each new deployment
    """
    def __init__(self):
        super(ResetContext, self).__init__()
        self.name = "reset-context"
        self.summary = "reset context for current job"
        self.description = "clear dynamic data from previous deployment"

    def run(self, connection, args=None):
        connection = super(ResetContext, self).run(connection, args)
        self.logger.debug("Resetting dynamic data from previous deployment")
        self.job.reset_context()
        return connection
