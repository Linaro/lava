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

from contextlib import contextmanager
from lava_dispatcher.context import LavaContext
from lava_dispatcher.pipeline import *


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
    """

    def __init__(self, parameters):
        self.parameters = parameters
        self.context = None

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        self.actions = pipeline.children

    @property
    def context(self):
        return self.context

    def __set_context__(self, data):
        self.__context__ = data

    @context.setter
    def context(self, data):
        self.__set_context__(data)

    def describe(self):
        return self.pipeline.describe()

    def validate(self):
        """
        Needs to validate the parameters
        Then needs to validate the context
        Finally expose the context so that actions can see it.
        """
        try:
            print yaml.dump(self.describe())  # FIXME: actually needs to validate
        except Exception as e:
            raise RuntimeError(e)

    def run(self):
        self.pipeline.run_actions(None, args=None)
        # FIXME how to get rootfs with multiple deployments, and at arbitrary
        # points in the pipeline?
        # rootfs = None
        # self.action.prepare(rootfs)

        # self.action.run(None)

        # FIXME how to know when to extract results with multiple deployment at
        # arbitrary points?
        # results_dir = None
        #    self.action.post_process(results_dir)

    def mkdtemp(self, basedir='/tmp'):
        """
        returns a temporary directory that's deleted when the process exits

        """
        # FIXME move to utils module?
        d = tempfile.mkdtemp(dir=basedir)
        atexit.register(rmtree, d)
        os.chmod(d, 0755)
        return d

    @property
    def scratch_dir(self):
        if self._scratch_dir is None:
            self._scratch_dir = self.mkdtemp(
                self.context.config.lava_image_tmpdir)
        return self._scratch_dir
