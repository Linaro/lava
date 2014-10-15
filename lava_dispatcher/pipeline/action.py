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
import time
import signal
import types
import yaml
import logging
import subprocess
from collections import OrderedDict
from contextlib import contextmanager
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
    filters standard logs into structured logs
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
        # FIXME: this should be a method from the Action class
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
        # FIXME: if this is only happening in unit test, this has to be fixed later on
        if self.job:  # should only be None inside the unit tests
            action.job = self.job
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
            if not os.path.exists(os.path.dirname(yaml_filename)):
                os.makedirs(os.path.dirname(yaml_filename))
            action.log_handler = logging.FileHandler(yaml_filename, mode='a', encoding="utf8")
            # per action loggers always operate in DEBUG mode - the frontend does the parsing later.
            action.log_handler.setLevel(logging.DEBUG)
            # yaml wrapper inside the log handler
            pattern = ' - id: "<LAVA_DISPATCHER>%(asctime)s"\n%(message)s'
            action.log_handler.setFormatter(logging.Formatter(pattern))
        # if the action has an internal pipeline, initialise that here.
        action.populate()

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

    def validate_actions(self):
        for action in self.actions:
            action.validate()

    def run_actions(self, connection, args=None):
        for action in self.actions:
            # TODO: moving all logger.getLogger at the top of each file (at
            # import time). Isn't it better to have one logger per action and
            # to create these loggers at creation time.
            yaml_log = None
            std_log = logging.getLogger("ASCII")
            # FIXME: this is not related to the log_handler. It's a side effect
            # that the log_handkler does create the output directory.
            if not action.log_handler:
                # FIXME: unit test needed
                # if no output dir specified in the job
                std_log.debug("no output-dir, logging %s:%s to stdout", action.level, action.name)
            else:
                yaml_log = logging.getLogger("YAML")  # allows per-action logs in yaml
                yaml_log.setLevel(logging.DEBUG)  # yaml log is always in debug
                # enable the log handler created in this action when it was added to this pipeline
                yaml_log.addHandler(action.log_handler)
                yaml_log.debug({'start': {action.level: action.name}})
            try:
                start = time.time()
                new_connection = action.run(connection, args)
                action.elapsed_time = time.time() - start
                action._log("duration: %.02f" % action.elapsed_time)
                if new_connection:
                    connection = new_connection
            except KeyboardInterrupt:
                action.cleanup()
                self.err = "\rCancel"  # Set a useful message.
                if self.parent:
                    raise KeyboardInterrupt
                break
            except (JobError, InfrastructureError) as exc:
                action.errors = exc.message
                action.results = {"fail": exc}
            # set results including retries
            if action.log_handler:
                # remove per-action log handler
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
        # FIXME: too many?
        self.__summary__ = None
        self.__description__ = None
        self.__level__ = None
        self.err = None
        self.pipeline = None
        self.internal_pipeline = None
        self.__parameters__ = {}
        self.yaml_line = None  # FIXME: should always be in parameters
        self.__errors__ = []
        self.elapsed_time = None  # FIXME: pipeline_data?
        self.log_handler = None
        self.job = None
        self.results = None
        # FIXME: what about {} for default value?
        self.env = None  # FIXME make this a parameter which gets default value when first called
        self.timeout = None  # Timeout class instance, if needed.

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

    # FIXME: dwhy do you need this function?
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

    # FIXME: dwhy do you need this function?
    def __set_summary__(self, summary):
        self.__summary__ = summary

    @property
    def data(self):
        """
        Shortcut to the job.context.pipeline_data
        """
        if not self.job:
            return None
        return self.job.context.pipeline_data

    @data.setter
    def data(self, value):
        """
        Accepts a dict to be updated in the job.context.pipeline_data
        """
        self.job.context.pipeline_data.update(value)

    # FIXME: has to be called select to be consistent with Deployment
    @classmethod
    def find(cls, name):
        for subclass in cls.__subclasses__():
            if subclass.name == name:
                return subclass
        raise KeyError("Cannot find action named \"%s\"" % name)

    @property
    def errors(self):
        return self.__errors__

    @errors.setter
    def errors(self, error):
        self._log(error)
        self.__errors__.append(error)

    @property
    def valid(self):
        return len([x for x in self.errors if x]) == 0

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

    # FIXME: dwhy do you need this function?
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
        if self.pipeline:
            for action in self.pipeline.actions:
                action.parameters = self.parameters

    def validate(self):
        """
        This method needs to validate the parameters to the action. For each
        validation that is found, an item should be added to self.errors.
        Validation includes parsing the parameters for this action for
        values not set or values which conflict.
        """
        if self.errors:
            self._log("Validation failed")
            raise JobError("Invalid job data: %s\n" % '\n'.join(self.errors))

    def populate(self):
        """
        This method allows an action to add an internal pipeline
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

    def _log(self, message):
        if not message:
            return
        # FIXME: why are we recreating the loggers everytime? Maybe having one
        # logger per action si easier to use. Calling it YAML.%(action_name)s
        yaml_log = logging.getLogger("YAML")
        std_log = logging.getLogger("ASCII")
        if type(message) is dict:
            for key, value in message.iteritems():
                yaml_log.debug("   %s: %s" % (key, value))
        else:
            yaml_log.debug("   log: \"%s\"" % message)
        std_log.info(message)

    def _run_command(self, command_list, env=None):
        """
        Single location for all external command operations on the
        dispatcher, without using a shell and with full structured logging.
        Ensure that output for the YAML logger is a serialisable object
        and strip embedded newlines / whitespace where practical.
        Returns the output of the command (after logging the output)
        Includes default support for proxy settings in the environment.
        Blocks until the command returns then processes & logs the output.
        """
        if type(command_list) != list:
            raise RuntimeError("commands to _run_command need to be a list")
        # FIXME: see logger
        yaml_log = logging.getLogger("YAML")
        log = None
        if not self.env:
            self.env = {'http_proxy': self.job.context.config.lava_proxy,
                        'https_proxy': self.job.context.config.lava_proxy}
        if env:
            self.env.update(env)
        # FIXME: distinguish between host and target commands and add 'nice' to host
        try:
            log = subprocess.check_output(command_list, stderr=subprocess.STDOUT, env=self.env)
        except KeyboardInterrupt:
            self.cleanup()
            self.err = "\rCancel"  # Set a useful message.
        except OSError as exc:
            yaml_log.debug({exc.strerror: exc.child_traceback.split('\n')})
        except subprocess.CalledProcessError as exc:
            self.errors = exc.message
            yaml_log.debug({
                'command': [i.strip() for i in exc.cmd],
                'message': [i.strip() for i in exc.message],
                'output': exc.output.split('\n')})
        self._log("%s\n%s" % (' '.join(command_list), log))
        return log

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
        raise NotImplementedError("run")

    def cleanup(self):
        # FIXME: perform() does not exist, is it run()?
        """
        This method *will* be called after perform(), no matter whether
        perform() raises an exception or not. It should cleanup any resources
        that may be left open by perform, such as, but not limited to:

            - open file descriptors
            - mount points
            - error codes
            - etc
        """
        raise NotImplementedError("cleanup")

    def post_process(self):
        """
        After tests finish running, the test results directory will be
        extracted, and passed to this method so that the action can
        inspect/extract its results.

        In this classs this method does nothing. It must be implemented by
        subclasses
        """
        raise NotImplementedError("post_process")

    def explode(self):
        """
        serialisation support
        """
        data = {}
        members = [attr for attr in dir(self) if not callable(attr) and not attr.startswith("__")]
        members.sort()
        for name in members:
            if name == "pipeline":
                continue
            content = getattr(self, name)
            if name == "job" or name == "log_handler" or name == "internal_pipeline":
                continue
            if name == "timeout":
                if content and not getattr(content, 'protected'):
                    content = {
                        'name': getattr(content, 'name'),
                        'duration': getattr(content, 'duration')
                    }
            if name == 'parameters':
                # FIXME: move deployment_data into the Job to save on repetition. Then output alongside the Device in Pipeline.
                if 'deployment_data' in content:
                    content = {
                        'deployment_data': content['deployment_data'].__data__
                    }
                else:
                    output = {'parameters': content}
                    content = output
            if isinstance(content, types.MethodType):
                continue
            if content:
                data[name] = content
        return data


class RetryAction(Action):

    def __init__(self):
        super(RetryAction, self).__init__()
        self.retries = 0
        # FIXME: have better dafault values. Should be seen somewhere in the
        # configuration or a constant in the code.
        self.max_retries = 5
        self.sleep = 1

    def run(self, connection, args=None):
        while self.retries <= self.max_retries:
            try:
                new_connection = self.run(connection)
                return new_connection
            except KeyboardInterrupt:
                # FIXME: calling cleanup two times!
                self.cleanup()
                self.err = "\rCancel"  # Set a useful message.
            except (JobError, InfrastructureError):
                # FIXME: print the retry cont like %(current_retry)d/%(max_retry)d
                self._log("%s failed, trying again" % self.name)
                self.retries += 1
                time.sleep(self.sleep)
            finally:
                # QUESTION: is it the right time to cleanup?
                self.cleanup()
        raise JobError("%s retries failed for %s" % (self.retries, self.name))

    def __call__(self, connection):
        self.run(connection)


class FinalizeAction(Action):

    def __init__(self):
        super(FinalizeAction, self).__init__()
        self.name = "finalize"
        self.summary = "finalize the job"
        self.description = "finish the process and cleanup"

    def run(self, connection, args=None):
        """
        The pexpect.spawn here is the ShellCommand not the ShellSession connection object.
        So call the finalise() function of the connection which knows about the raw_connection inside.
        """
        if connection:
            connection.finalise()


class Deployment(object):  # pylint: disable=abstract-class-not-used
    """
    Deployment is a strategy class which aggregates Actions
    until the request from the YAML can be validated or rejected.
    Translates the parsed pipeline into Actions and populates
    each Action with parameters.
    Primary purpose of the Deployment class is to allow the
    parser to select the correct deployment before initialising
    any Actions.
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
        copied directly from the YAML or Device configuration.
        Dynamic data is held in the context available via the parent Pipeline()
        """
        return self.__parameters__

    def __set_parameters__(self, data):
        self.__parameters__.update(data)

    @parameters.setter
    def parameters(self, data):
        self.__set_parameters__(data)

    @classmethod
    def accepts(cls, device, parameters):  # pylint: disable=unused-argument
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
                "device '%s'." % device.parameters['hostname'])

        # higher priority first
        compare = lambda x, y: cmp(y.priority, x.priority)
        prioritized = sorted(willing, compare)

        return prioritized[0]


class Boot(object):
    """
    Allows selection of the boot method for this job within the parser.
    """

    priority = 0

    def __init__(self, parent):
        self.__parameters__ = {}
        self.pipeline = parent
        self.job = parent.job

    @classmethod
    def accepts(cls, device, parameters):  # pylint: disable=unused-argument
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
                "No boot strategy available for the device "
                "'%s' with the specified job parameters" % device.parameters['hostname']
            )

        # higher priority first
        compare = lambda x, y: cmp(y.priority, x.priority)
        prioritized = sorted(willing, compare)

        return prioritized[0]


class LavaTest(object):  # pylint: disable=abstract-class-not-used
    """
    Allows selection of the boot method for this job within the parser.
    """

    priority = 0

    def __init__(self, parent):
        self.__parameters__ = {}
        self.pipeline = parent
        self.job = parent.job

    @contextmanager
    def boot(self):
        """
        This method must be implemented by subclasses.
        """
        raise NotImplementedError("test")

    @classmethod
    def accepts(cls, device, parameters):  # pylint: disable=unused-argument
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
                "No test strategy available for the device "
                "'%s' with the specified job parameters" % device.parameters['hostname']
            )

        # higher priority first
        compare = lambda x, y: cmp(y.priority, x.priority)
        prioritized = sorted(willing, compare)

        return prioritized[0]


class Image(object):  # pylint: disable=abstract-class-not-used
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


class Timeout(object):
    """
    The Timeout class is a declarative base which any actions can use. If an Action has
    a timeout, that timeout name and the duration will be output as part of the action
    description and the timeout is then exposed as a modifiable value via the device_type,
    device or even job inputs. (Some timeouts may be deemed "protected" which may not be
    altered by the job. All timeouts are subject to a hardcoded maximum duration which
    cannot be exceeded by device_type, device or job input, only by the Action initialising
    the timeout.
    """

    def __init__(self, name, duration=30, protected=False):
        self.name = name
        self.duration = duration  # Actions can set timeouts higher than the clamp.
        self.protected = protected

    @classmethod
    def default_duration(cls):
        return 30

    def modify(self, duration):
        """
        Called from the parser if the job or device YAML wants to set an override.
        """
        if self.protected:
            raise JobError("Trying to modify a protected timeout: %s.", self.name)
        clamp = lambda n, minn, maxn: max(min(maxn, n), minn)
        self.duration = clamp(duration, 1, 300)


class Connection(object):
    """
    A raw_connection is an arbitrary instance of a standard Python (or added LAVA) class
    designed to implement an interactive connection onto the device. The raw_connection
    needs to be able to send commands, use a timeout, handle errors, log the output,
    match on regular expressions for the output, report the pid of the spawned process
    and cause the spawned process to close/terminate.
    The current implementation uses a pexpect.spawn wrapper. For a standard Shell
    connection, that is the ShellCommand class.
    Each different wrapper of pexpect.spawn (and any other wrappers later designed)
    needs to be a separate class supported by another class inheriting from Connection.
    """
    def __init__(self, device, raw_connection):
        self.device = device
        self.raw_connection = raw_connection

    def sendline(self, line):
        self.raw_connection.sendline(line)

    def finalise(self):
        if self.raw_connection:
            yaml_log = logging.getLogger("YAML")
            try:
                os.killpg(self.raw_connection.pid, signal.SIGKILL)
                yaml_log.debug("Finalizing child process group with PID %d" % self.raw_connection.pid)
            except OSError:
                connection.kill(9)
                yaml_log.debug("Finalizing child process with PID %d" % self.raw_connection.pid)
            self.raw_connection.close()


class Device(object):
    """
    Holds all data about the device for this TestJob including
    all database parameters and device condfiguration.
    In the dumb dispatcher model, an instance of Device would
    be populated directly from the master scheduler.
    """

    def __init__(self, hostname):
        self.config = get_device_config(hostname)
