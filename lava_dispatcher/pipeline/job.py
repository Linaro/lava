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

import os
import atexit
import yaml
import tempfile
import subprocess
from collections import OrderedDict
from lava_dispatcher.utils import rmtree
from lava_dispatcher.pipeline.diagnostics import DiagnoseNetwork
from lava_dispatcher.pipeline.action import PipelineContext


class Job(object):
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

    def __init__(self, parameters):
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
        structure = OrderedDict()
        structure['device'] = {
            'parameters': self.device.parameters
        }
        structure['job'] = {
            'parameters': self.parameters
        }
        # FIXME: output the deployment data here and remove from the Actions
        structure.update(self.pipeline.describe())
        return structure

    def validate(self, simulate=False):
        """
        Needs to validate the parameters
        Then needs to validate the context
        Finally expose the context so that actions can see it.
        """
        if simulate:
            # output the content and then any validation errors
            print yaml.dump(self.describe())
        # FIXME: validate the device config
        # FIXME: pretty output of exception messages needed.
        self.pipeline.validate_actions()

    def run(self):
        """
        Top level routine for the entire life of the Job.
        """
        self.pipeline.run_actions(self.connection)  # FIXME: some Deployment methods may need to set a Connection.
        # FIXME how to get rootfs with multiple deployments, and at arbitrary
        # points in the pipeline?
        # rootfs = None
        # self.action.prepare(rootfs)

        # self.action.run(None)

        # FIXME how to know when to extract results with multiple deployment at
        # arbitrary points?
        # results_dir = None
        #    self.action.post_process(results_dir)

    # FIXME: should be moved to a specific helper module
    def rmtree(self, directory):
        # FIXME: change to self._run_command
        subprocess.call(['rm', '-rf', directory])

    # FIXME: should be moved to a specific helper module
    def mkdtemp(self, basedir='/tmp'):
        """
        returns a temporary directory that's deleted when the process exits

        """
        # FIXME move to utils module?
        tmpdir = tempfile.mkdtemp(dir=basedir)
        atexit.register(rmtree, tmpdir)
        os.chmod(tmpdir, 0o755)
        return tmpdir
