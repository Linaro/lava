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
import sys
import types
import yaml
import logging
from collections import OrderedDict
from contextlib import contextmanager
from lava_dispatcher.context import LavaContext
from lava_dispatcher.config import get_device_config


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


class YamlFilter(logging.Filter):
    """
    filters standard logs into structued logs
    """
    def filter(self, record):
        record.msg = yaml.dump(record.msg)
        return True


class Pipeline(object):
    """
    Pipelines ensure that actions are run in the correct sequence whilst
    allowing for retries and other requirements.
    When an action is added to a pipeline, the level of that action within
    the overall job is set along with the formatter and output filename
    of the per-action log handler.
    """
    def __init__(self, parent=None, job=None):
        self.children = {}
        self.actions = []
        self.summary = "pipeline"
        self.parent = None
        self.job = None
        self.branch_level = 1  # the level of the last added child
        if job:  # do not unset if set by outer pipeline
            self.job = job
        if not parent:
            self.children = {self: self.actions}
        elif not parent.level:
            raise RuntimeError("Tried to create a pipeline using a parent action with no level set.")
        else:
            # parent must be an Action
            if not isinstance(parent, Action):
                raise RuntimeError("Internal pipelines need an Action as a parent")
            self.parent = parent
            self.branch_level = parent.level
            if parent.job:
                self.job = parent.job

    def _check_action(self, action):
        if not action or not issubclass(type(action), Action):
            raise RuntimeError("Only actions can be added to a pipeline: %s" % action)
        if not action:
            raise RuntimeError("Unable to add empty action to pipeline")
        if not action.name:
            raise RuntimeError("Unnamed action!")
        if ' ' in action.name:
            raise RuntimeError("Whitespace must not be used in action names, only descriptions or summaries")

    def add_action(self, action):
        self._check_action(action)
        self.actions.append(action)
        action.level = "%s.%s" % (self.branch_level, len(self.actions))
        if action.job:  # should only be None inside the unit tests
            self.job = action.job
        if self.parent:  # action
            self.children.update({self: self.actions})
            self.parent.pipeline = self
        else:
            action.level = "%s" % (len(self.actions))
        # create a log handler just for this action.
        if self.job and self.job.parameters['output_dir']:
            yaml_filename = os.path.join(
                self.job.parameters['output_dir'],
                "%s-%s.log" % (action.level, action.name)
            )
            action.log_handler = logging.FileHandler(yaml_filename, mode='a', encoding="utf8")
            # per action loggers always operate in DEBUG mode - the frontend does the parsing later.
            action.log_handler.setLevel(logging.DEBUG)
            # yaml wrapper inside the log handler
            action.log_handler.setFormatter(logging.Formatter('id: "<LAVA_DISPATCHER>%(asctime)s"\n%(message)s'))

    def _describe(self, structure):
        # TODO: make the amount of output conditional on a parameter passed to describe
        for action in self.actions:
            structure[action.level] = {
                'description': action.description,
                'summary': action.summary,
                'content': action.explode()
            }
            if not action.pipeline:
                continue
            action.pipeline._describe(structure)

    def describe(self):
        """
        Describe the current pipeline, recursing through any
        internal pipelines.
        :return: JSON string of the structure
        """
        structure = OrderedDict()
        self._describe(structure)
        return structure

    @property
    def errors(self):
        sub_action_errors = [a.errors for a in self.actions]
        return reduce(lambda a, b: a + b, sub_action_errors)

    def run_actions(self, connection, args=None):
        context = None
        if isinstance(args, LavaContext):
            context = args
            # FIXME: single location in the job?
            yaml_log = logging.getLogger("YAML")  # allows per-action logs in yaml
            yaml_log.setLevel(logging.DEBUG)  # yaml log is always in debug
            std_log = logging.getLogger("ASCII")
        for action in self.actions:
            # enable the log handler created in this action when it was added to this pipeline
            # FIXME: determine how this works with internal pipelines & whether any duplication is warranted.
            if context:
                yaml_log.addHandler(action.log_handler)
                yaml_log.debug({'start': {action.level: action.name}})
            new_connection = action.run(connection, context)
            if new_connection:
                connection = new_connection
            # remove per-action log handler
            if context:
                yaml_log.removeHandler(action.log_handler)
        return connection

    def prepare_actions(self):
        for action in self.actions:
            action.prepare()

    def post_process_actions(self):
        for action in self.actions:
            action.post_process()


class Action(object):

    def __init__(self):
        """
        Actions get added to pipelines by calling the
        Pipeline.add_action function. Other Action
        data comes from the parameters. Actions with
        internal pipelines push parameters to actions
        within those pipelines. Parameters are to be
        treated as inmutable.

        Logs written to the per action log must use the YAML logger.
        Output for stdout (which is redirected to the oob_file by the
        scheduler) should use the ASCII logger.
        yaml_log = logging.getLogger("YAML")
        std_log = logging.getLogger("ASCII")
        """
        self.__summary__ = None
        self.__description__ = None
        self.__level__ = None
        self.err = None
        self.pipeline = None
        self.__parameters__ = {}
        self.yaml_line = None
        self.__errors__ = []
        self.elapsed_time = None
        self.log_handler = None
        self.job = None

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
        if self.pipeline:
            for action in self.pipeline.actions:
                action.parameters = self.parameters

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

    def _run_command(self, command_list):
        """
        Single location for all external command operations, without using
        a shell and with full structured logging.
        Ensure that output for the YAML logger is a serialisable object
        and strip embedded newlines / whitespace where practical.
        """
        if type(command_list) != list:
            raise RuntimeError("commands to _run_command need to be a list")
        yaml_log = logging.getLogger("YAML")
        std_log = logging.getLogger("ASCII")
        log = None
        try:
            log = subprocess.check_output(command_list, stderr=subprocess.STDOUT)
        except KeyboardInterrupt:
            self.cleanup()
            self.err = "\rCancel"  # Set a useful message.
        except OSError as e:
            yaml_log.debug({e.strerror: e.child_traceback.split('\n')})
        except subprocess.CalledProcessError as e:
            yaml_log.debug({
                'command': [i.strip() for i in e.cmd],
                'message': [i.strip() for i in e.message],
                'output': e.output.split('\n')})
        if log:
            yaml_log.debug({"output": log.split('\n')})
            std_log.info(log)
        else:
            # FIXME: no output may be correct - add a flag to allow RuntimeError if not
            pass
        # FIXME: return False on error?

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


class RetryAction(Action):

    def __init__(self):
        super(RetryAction, self).__init__()
        self.retries = 5

    def run(self, connection, args=None):
        pass

    def __call__(self, connection):
        while self.retries:
            try:
                new_connection = self.run(connection)
                return new_connection
            except JobError:
                self.retries -= 1
            finally:
                self.cleanup()


class Deployment(object):
    """
    Deployment is a  strategy class which aggregates Actions
    until the request from the YAML can be validated or rejected.
    Translates the parsed pipeline into Actions and populates
    each Action with parameters.
    """

    priority = 0

    def __init__(self, parent):
        self.__parameters__ = {}
        self.pipeline = parent
        self.job = parent.job

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

    @classmethod
    def accepts(cls, device, parameters):
        """
        Returns True if this deployment strategy can be used the the
        given device and details of an image in the parameters.

        Must be implemented by subclasses.
        """
        return NotImplementedError("accepts")

    @classmethod
    def select(cls, device, parameters):

        candidates = cls.__subclasses__()
        willing = [c for c in candidates if c.accepts(device, parameters)]

        if len(willing) == 0:
            raise NotImplementedError(
                "No deployment strategy available for the given "
                "device '%s'." % device.config.hostname)

        # higher priority first
        compare = lambda x, y: cmp(y.priority, x.priority)
        prioritized = sorted(willing, compare)

        return prioritized[0]


class Image(object):
    """
    Create subclasses for each type of image: prebuilt, hwpack+rootfs,
    kernel+rootfs+dtb+..., dummy, ...
    TBD: this might not be needed.
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
    """
    Holds all data about the device for this TestJob including
    all database parameters and device condfiguration.
    In the dumb dispatcher model, an instance of Device would
    be populated directly from the master scheduler.
    """

    def __init__(self, hostname):
        self.config = get_device_config(hostname)
