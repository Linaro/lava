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

import sys
import simplejson
import types
from contextlib import contextmanager


class InfrastructureError(Exception):
    """
    Exceptions based on an error raised by a component of the
    test which is neither the LAVA dispatcher code nor the
    code being executed on the device under test. This includes
    errors arising from the device (like the arndale SD controller
    issue) and errors arising from the hardware to which the device
    is connected (serial console connection, ethernet switches or
    internet connection beyond the control of the device under test).

    Use the existing RuntimeError exception for errors arising
    from bugs in LAVA code.
    """
    pass


class JobError(Exception):
    """
    An Error arising from the information supplied as part of the TestJob
    e.g. HTTP404 on a file to be downloaded as part of the preparation of
    the TestJob or a download which results in a file which tar or gzip
    does not recognise.
    """
    pass


class TestError(Exception):
    """
    An error in the operation of the test definition.
    """
    pass


class Action(object):

    def __init__(self, line=None):
        self.__summary__ = None
        self.__description__ = None
        self.__level__ = None
        self.err = None
        self.pipeline = None
        self.__parameters__ = {}
        self.yaml_line = line
        self.__errors__ = []

    # public actions (i.e. those who can be referenced from a job file) must
    # declare a 'class-type' name so they can be looked up.
    # summary and description are used to identify instances.
    name = None

    @property
    def description(self):
        """
        The description of the command, set by each instance of
        each class inheriting from Action.
        Used in the pipeline to explain what the commands will
        attempt to do.
        :return: a string created by the instance.
        """
        return self.__description__

    @description.setter
    def description(self, description):
        self.__set_desc__(description)

    def __set_desc__(self, desc):
        self.__description__ = desc

    @property
    def summary(self):
        """
        A short summary of this instance of a class inheriting
        from Action. May be None.
        Can be used in the pipeline to summarise what the commands
        will attempt to do.
        :return: a string or None.
        """
        return self.__summary__

    @summary.setter
    def summary(self, summary):
        self.__set_summary__(summary)

    def __set_summary__(self, summary):
        self.__summary__ = summary

    @classmethod
    def find(cls, name):
        for subclass in cls.__subclasses__():
            if subclass.name == name:
                return subclass
        raise KeyError("Cannot find action named \"%s\"" % name)

    @property
    def errors(self):
        return self.__errors__

    @property
    def valid(self):
        return len(self.errors) == 0

    @property
    def level(self):
        """
        The level of this action within the pipeline. Levels
        start at one and each pipeline within an command uses
        a level within the level of the parent pipeline.
        First command in Outer pipeline: 1
        First command in pipeline within outer pipeline: 1.1
        level is set during pipeline creation and must not
        be changed subsequently except by RetryCommand..
        :return: a string
        """
        return self.__level__

    @level.setter
    def level(self, value):
        self.__set_level__(value)

    def __set_level__(self, value):
        self.__level__ = value

    @property
    def parameters(self):
        """
        All data which this action needs to have available for
        the prepare, run or post_process functions needs to be
        set as a parameter. The parameters will be validated
        during pipeline creation.
        This allows all pipelines to be fully described, including
        the parameters supplied to each action, as well as supporting
        tests on each parameter (like 404 or bad formatting) during
        validation of each action within a pipeline.
        Parameters are static, internal data within each action
        copied directly from the YAML. Dynamic data is held in
        the context available via the parent Pipeline()
        """
        return self.__parameters__

    def __set_parameters__(self, data):
        self.__parameters__.update(data)

    @parameters.setter
    def parameters(self, data):
        self.__set_parameters__(data)

    def validate(self):
        """
        This method needs to validate the parameters to the action. For each
        validation that is found, an item should be added to self.errors.
        Validation includes parsing the parameters for this action for
        values not set or values which conflict.
        """
        pass

    def prepare(self):
        """
        This method will be called before deploying an image to the target,
        being passed a local mount point with the target root filesystem. This
        method will then have a chance to modify the root filesystem, including
        editing existing files (which should be used with caution) and adding
        new ones. Any modifications done will be reflected in the final image
        which is deployed to the target.

        In this classs this method does nothing. It must be implemented by
        subclasses
        """
        pass

    def __call__(self, connection):
        try:
            new_connection = self.run(connection)
            return new_connection
        finally:
            self.cleanup()

    def run(self, connection, args=None):
        """
        This method is responsible for performing the operations that an action
        is supposed to do.

        This method usually returns nothing. If it returns anything, that MUST
        be an instance of Connection. That connection will be the one passed on
        to the next action in the pipeline.

        In this classs this method does nothing. It must be implemented by
        subclasses

        :param args: Command and arguments to run
        :raise: Classes inheriting from BaseAction must handle
        all exceptions possible from the command and re-raise
        KeyboardInterrupt to allow for Cancel operations. e.g.:

        try:
            # call the command here
        except KeyboardInterrupt:
            self.cleanup()
            self.err = "\rCancel"  # Set a useful message.
            sys.exit(1)  # Only in the top level pipeline
        except Exception as e:
            raise e
        finally:
            self.cleanup()
            if self.err:
                print self.err
        """
        pass

    def cleanup(self):
        """
        This method *will* be called after perform(), no matter whether
        perform() raises an exception or not. It should cleanup any resources
        that may be left open by perform, such as, but not limited to:

            - open file descriptors
            - mount points
            - error codes
            - etc
        """
        try:
            raise
        except:
            sys.exc_clear()

    def post_process(self):
        """
        After tests finish running, the test results directory will be
        extracted, and passed to this method so that the action can
        inspect/extract its results.

        In this classs this method does nothing. It must be implemented by
        subclasses
        """
        pass

    def explode(self):
        """
        serialisation support
        """
        data = {}
        members = [attr for attr in dir(self) if not callable(attr) and not attr.startswith("__")]
        for name in members:
            if name == "pipeline":
                continue
            content = getattr(self, name)
            if isinstance(content, types.MethodType):
                continue
            data[name] = content
        return data


class Deployment(object):

    priority = 0

    @contextmanager
    def deploy(self):
        """
        This method first mounts the image locally, exposing its root
        filesystem in a local directory which will be yielded to the
        caller, which has the chance to modify the contents of the root
        filesystem.

        Then, the root filesystem will be unmounted and the image will
        be deployed to the device.

        This method must be implemented by subclasses.
        """
        raise NotImplementedError("deploy")

    @contextmanager
    def extract_results(self):
        """
        This method will extract the results directory from the root filesystem
        in the device. After copying that directory locally, the local copy
        will be yielded to the caller, who can read data from it.

        Must be implemented by subclasses.
        """
        raise NotImplementedError("extract_results")

    @classmethod
    def accepts(self, device, image):
        """
        Returns True if this deployment strategy can be used the the
        given device and image.

        Must be implemented by subclasses.
        """
        return NotImplementedError("accepts")

    @classmethod
    def select(cls, device, image):

        candidates = cls.__subclasses__()
        willing = [c for c in candidates if c.accepts(device, image)]

        if len(willing) == 0:
            raise NotImplementedError(
                "No deployment strategy available for the given image "
                "on the given device.")

        # higher priority first
        compare = lambda x, y: cmp(y.priority, x.priority)
        prioritized = sorted(willing, compare)

        return prioritized[0]


class Job(object):

    def __init__(self, pipeline, parameters):
        self.pipeline = pipeline
        self.actions = pipeline.children
        self.parameters = parameters

    def run(self):

        # FIXME how to get rootfs with multiple deployments, and at arbitrary
        # points in the pipeline?
        rootfs = None
        self.action.prepare(rootfs)

        self.action.run(None)

        # FIXME how to know when to extract results with multiple deployment at
        # arbitrary points?
        results_dir = None
        #    self.action.post_process(results_dir)


class Image(object):
    """
    Create subclasses for each type of image: prebuilt, hwpack+rootfs,
    kernel+rootfs+dtb+..., dummy, ...
    """

    @contextmanager
    def mount_rootfs(self):
        """
        Subclasses must implement this method
        """
        raise NotImplementedError("mount_rootfs")


class Connection(object):

    def __init__(self, device, raw_connection):
        self.device = device
        self.raw_connection = raw_connection


class Device(object):

    def __init__(self, hostname):
        self.config = get_device_config(hostname)
