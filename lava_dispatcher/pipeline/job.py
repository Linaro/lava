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
import time
import yaml

from lava_dispatcher.pipeline.action import Action, JobError, InfrastructureError
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

    def __init__(self, job_id, socket_addr, master_cert, slave_cert, parameters):
        self.job_id = job_id
        self.socket_addr = socket_addr
        self.master_cert = master_cert
        self.slave_cert = slave_cert
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
        self.compatibility = 2
        # We are now able to create the logger when the job is started,
        # allowing the functions that are called before run() to log.
        # The validate() function is no longer called on the master so we can
        # safelly add the ZMQ handler. This way validate can log errors that
        # test writter will see.
        self.logger = logging.getLogger('dispatcher')
        if socket_addr is not None:
            self.logger.addZMQHandler(socket_addr, master_cert, slave_cert,
                                      job_id)
            self.logger.setMetadata("0", "validate")
        else:
            self.logger.addHandler(logging.StreamHandler())

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        self.actions = pipeline.children

    @property
    def context(self):
        return self.__context__.pipeline_data

    @context.setter
    def context(self, data):
        self.__context__.pipeline_data.update(data)

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
                'compatibility': self.compatibility,
                'pipeline': self.pipeline.describe()}

    def validate(self, simulate=False):
        """
        Needs to validate the parameters
        Then needs to validate the context
        Finally expose the context so that actions can see it.
        """
        self.logger.info("start: 0 validate")
        start = time.time()
        for protocol in self.protocols:
            try:
                protocol.configure(self.device, self)
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
        if simulate:
            # output the content and then any validation errors (python3 compatible)
            print(yaml.dump(self.describe()))  # pylint: disable=superfluous-parens
        # FIXME: validate the device config
        # FIXME: pretty output of exception messages needed.
        try:
            self.pipeline.validate_actions()
        except (JobError, InfrastructureError) as exc:
            self.logger.error("Invalid job definition")
            self.logger.exception(str(exc))
            # This should be re-raised to end the job
            raise
        finally:
            self.logger.info("validate duration: %.02f", time.time() - start)

    def run(self):
        """
        Top level routine for the entire life of the Job, using the job level timeout.
        Python only supports one alarm on SIGALRM - any Action without a connection
        will have a default timeout which will use SIGALRM. So the overarching Job timeout
        can only stop processing actions if the job wide timeout is exceeded.
        """
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
