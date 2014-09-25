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


class Job(object):
    """
    Populated by the parser, the Job contains all of the
    Actions and their pipelines.
    parameters provides:
        action_timeout
        job_name
        priority
        device_type (mapped to target by scheduler)
        yaml_line
        logging_level
        job_timeout
    Job also provides the primary access to the Device.
    """

    def __init__(self, parameters):
        self.device = None
        self.parameters = parameters
        self.__context__ = None
        self.pipeline = None
        self.actions = None
        self._scratch_dir = None
        self.connection = None

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        self.actions = pipeline.children

    @property
    def context(self):
        return self.__context__

    @context.setter
    def context(self, data):
        self.__context__ = data

    def describe(self):
        structure = OrderedDict()
        # FIXME: port to the updated Device configuration
        structure['device'] = {
            'parameters': self.device.parameters
        }
        structure['job'] = {
            'parameters': self.parameters
        }
        # FIXME: output the deployment data here and remove from the Actions
        structure.update(self.pipeline.describe())
        return structure

    # FIXME: what about having one base class for all the classes that have
    # (prepare, validate, run, cleanup)?
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

    @property
    def scratch_dir(self):
        if self._scratch_dir is None:
            self._scratch_dir = self.mkdtemp(
                self.context.config.lava_image_tmpdir)
        return self._scratch_dir
