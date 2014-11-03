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
import types
import yaml
import logging
import datetime
import subprocess
import collections
from collections import OrderedDict
from contextlib import contextmanager

if sys.version > '3':
    from functools import reduce  # pylint: disable=redefined-builtin


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
    An error in the operation of the test definition, e.g.
    in parsing measurements or commands which fail.
    """
    # FIXME: ensure TestError is caught, logged and cleared. It is not fatal.
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
    def __init__(self, parent=None, job=None, parameters=None):
        self.children = {}
        self.actions = []
        self.summary = "pipeline"
        self.parent = None
        if parameters is None:
            parameters = {}
        self.parameters = parameters
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
        if isinstance(action, DiagnosticAction):
            raise RuntimeError("Diagnostic actions need to be triggered, not added to a pipeline.")
        if not action:
            raise RuntimeError("Unable to add empty action to pipeline")
        # FIXME: these should be part of the validate from the base Action class
        if not action.name:
            raise RuntimeError("Unnamed action!")
        if ' ' in action.name:
            raise RuntimeError("Whitespace must not be used in action names, only descriptions or summaries")

    def add_action(self, action, parameters=None):
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

        # Use the pipeline parameters if the function was walled without
        # parameters.
        if parameters is None:
            parameters = self.parameters
        # if the action has an internal pipeline, initialise that here.
        action.populate(parameters)
        # Set the parameters after populate so the sub-actions are also
        # getting the parameters.
        action.parameters = parameters

    def _generate(self, actions_list):
        actions = iter(actions_list)
        while actions:
            action = actions.next()
            # yield the action containing the pipeline
            yield {
                action.level: {
                    'description': action.description,
                    'summary': action.summary,
                    'content': action.explode()
                }
            }
            # now yield the pipeline to add the nested actions after the containing action.
            if action.pipeline:
                yield action.pipeline

    def _describe(self, structure):
        # TODO: make the amount of output conditional on a parameter passed to describe

        for data in self._generate(self.actions):
            if isinstance(data, Pipeline):  # recursion into sublevels
                data._describe(structure)
            else:
                structure.update(data)

    def describe(self):
        """
        Describe the current pipeline, recursing through any
        internal pipelines.
        :return: JSON string of the structure
        """
        structure = OrderedDict()
        self._describe(structure)
        # from meliae import scanner
        # scanner.dump_all_objects('/tmp/lava-describe.json')
        return structure

    @property
    def errors(self):
        sub_action_errors = [a.errors for a in self.actions]
        return reduce(lambda a, b: a + b, sub_action_errors)

    def validate_actions(self):
        for action in self.actions:
            action.validate()

    def _diagnose(self, connection):
        """
        Pipeline Jobs have a number of Diagnostic classes registered - all
        supported DiagnosticAction classes should be registered with the Job.
        If an Action.run() function reports a JobError or InfrastructureError,
        the Pipeline calls Job.diagnose(). The job iterates through the DiagnosticAction
        classes declared in the diagnostics list, checking if the trigger classmethod
        matches the requested complaint. Matching diagnostics are run using the current Connection.
        Actions generate a complaint by appending the return of the trigger classmethod
        to the triggers list of the Job. This can be done at any point prior to the
        exception being raised in the run function.
        The trigger list is cleared after each diagnostic operation is complete.
        """
        for complaint in self.job.triggers:
            diagnose = self.job.diagnose(complaint)
            if diagnose:
                connection = diagnose.run(connection, None)
            else:
                raise RuntimeError("No diagnosis for trigger %s" % complaint)
        self.job.triggers = []
        # Diagnosis is not allowed to alter the connection, do not use the return value.
        return None

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
                yaml_log.debug('   start:', {action.level: action.name})
            try:
                start = time.time()
                new_connection = action.run(connection, args)
                action.elapsed_time = time.time() - start
                action._log("duration: %.02f" % action.elapsed_time)
                if action.results:
                    action._log({"results": action.results})
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
                self._diagnose(connection)
                raise exc
            # FIXME: should we call the cleanup function here? Only the
            #        KeyboardInterrupt case does run cleanup.
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
        self.__results__ = OrderedDict()
        # FIXME: what about {} for default value?
        self.env = None  # FIXME make this a parameter which gets default value when first called
        self.timeout = None  # Timeout class instance, if needed.
        self.max_retries = 1  # unless the strategy or the job parameters change this, do not retry
        self.diagnostics = []

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
        self.__description__ = description

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
        self.__summary__ = summary

    @property
    def data(self):
        """
        Shortcut to the job.context
        """
        if not self.job:
            return None
        return self.job.context

    @data.setter
    def data(self, value):
        """
        Accepts a dict to be updated in the job.context
        """
        self.job.context.update(value)

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
        try:
            self.__parameters__.update(data)
        except ValueError:
            raise RuntimeError("Action parameters need to be a dictionary")
        self.timeout = Timeout('default')
        if 'timeout' in self.parameters:
            # FIXME: a top level timeout should cover all actions within the pipeline, not each action have the same timeout.
            time_str = self.parameters['timeout'][:-1]
            time_int = 0
            try:
                time_int = int(time_str)
            except ValueError:
                self.errors = "%s - Could not convert timeout: %s to an integer" % (self.name, time_str)
            if time_int:
                # FIXME: use a standard timeparsing module instead of inventing another confusing syntax.
                if self.parameters['timeout'].endswith('m'):
                    self.timeout = Timeout(self.name, datetime.timedelta(minutes=time_int).total_seconds())
                elif self.parameters['timeout'].endswith('h'):
                    self.timeout = Timeout(self.name, datetime.timedelta(hours=time_int).total_seconds())
                elif self.parameters['timeout'].endswith('s'):
                    self.timeout = Timeout(self.name, time_int)
        if 'failure_retry' in self.parameters:
            self.max_retries = self.parameters['failure_retry']

    @parameters.setter
    def parameters(self, data):
        self.__set_parameters__(data)
        if self.pipeline:
            for action in self.pipeline.actions:
                action.parameters = self.parameters

    @property
    def results(self):
        """
        Updated dictionary of results for this action.
        """
        return self.__results__

    @results.setter
    def results(self, data):
        try:
            self.__results__.update(data)
        except ValueError:
            raise RuntimeError("Action results need to be a dictionary")

    def validate(self):
        """
        This method needs to validate the parameters to the action. For each
        validation that is found, an item should be added to self.errors.
        Validation includes parsing the parameters for this action for
        values not set or values which conflict.
        """
        if not self.name:
            self.errors = "%s action has no name set" % self
        if ' ' in self.name:
            self.errors = "Whitespace must not be used in action names, only descriptions or summaries: %s" % self.name
        if self.internal_pipeline:
            self.internal_pipeline.validate_actions()
        if self.errors:
            self._log("Validation failed")
            raise JobError("Invalid job data: %s\n" % '\n'.join(self.errors))

    def populate(self, parameters):
        """
        This method allows an action to add an internal pipeline.
        The parameters are used to configure the internal pipeline on the
        fly.
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
        # FIXME: is this still relevant?
        pass

    def __call__(self, connection):
        # FIXME: necessary?
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
            for key, value in list(message.items()):
                yaml_log.debug("   %s: %s", key, value)
        else:
            yaml_log.debug("   log: \"%s\"", message)
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
        # FIXME: define a method of configuring the proxy for the pipeline.
        # if not self.env:
        #     self.env = {'http_proxy': self.job.context.config.lava_proxy,
        #                 'https_proxy': self.job.context.config.lava_proxy}
        if env:
            self.env.update(env)
        # FIXME: distinguish between host and target commands and add 'nice' to host
        try:
            log = subprocess.check_output(command_list, stderr=subprocess.STDOUT, env=self.env)
        except KeyboardInterrupt:
            self.cleanup()
            self.err = "\rCancel"  # Set a useful message.
            yaml_log.debug("Cancelled")
            return None
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
        if self.internal_pipeline:
            return self.internal_pipeline.run_actions(connection, args)
        raise NotImplementedError("run %s" % self.name)

    def cleanup(self):
        """
        This method *will* be called after run(), no matter whether
        run() raises an exception or not. It should cleanup any resources
        that may be left open by perform, such as, but not limited to:

            - open file descriptors
            - mount points
            - error codes
            - etc
        """
        pass

    def post_process(self):
        """
        After tests finish running, the test results directory will be
        extracted, and passed to this method so that the action can
        inspect/extract its results.

        Most Actions except TestAction will not have anything to do here.
        In this classs this method does nothing. It must be implemented by
        subclasses
        """
        # FIXME: with the results inside the pipeline already, is this needed?
        pass

    def explode(self):
        """
        serialisation support
        """
        # FIXME: convert to generators for each particular handler
        data = {}
        members = [attr for attr in dir(self)
                   if not isinstance(attr, collections.Callable) and not attr.startswith("__")]
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
        self.sleep = 1

    def validate(self):
        """
        The reasoning here is that the RetryAction should be in charge of an internal pipeline
        so that the retry logic only occurs once and applies equally to the entire pipeline
        of the retry.
        """
        super(RetryAction, self).validate()
        if not self.internal_pipeline:
            raise RuntimeError("Retry action %s needs to implement an internal pipeline" % self.name)

    def run(self, connection, args=None):
        while self.retries < self.max_retries:
            try:
                new_connection = self.internal_pipeline.run_actions(connection)
                return new_connection
            except KeyboardInterrupt:
                self.err = "\rCancel"  # Set a useful message.
                self.errors = "Cancelled"
                return connection
            except (JobError, InfrastructureError, TestError):
                self.retries += 1
                msg = "%s failed: %d of %d attempts." % (self.name, self.retries, self.max_retries)
                self.errors = msg
                self._log(msg)
                time.sleep(self.sleep)
            finally:
                # TODO: QUESTION: is it the right time to cleanup?
                self.cleanup()
        self.errors = "%s retries failed for %s" % (self.retries, self.name)
        self._log("%s retries failed for %s" % (self.retries, self.name))

    def __call__(self, connection):
        self.run(connection)


class DiagnosticAction(Action):  # pylint: disable=abstract-class-not-used

    def __init__(self):
        """
        Base class for actions which are run only if a failure is detected.
        Diagnostics have no level and are not intended to be added to Pipeline.
        """
        super(DiagnosticAction, self).__init__()
        self.name = "diagnose"
        self.summary = "diagnose action failure"
        self.description = "action-specific diagnostics in case of failure"

    @classmethod
    def trigger(cls):
        raise NotImplementedError("Define in the subclass: %s" % cls)

    def run(self, connection, args=None):
        """
        Log the requested diagnostic.
        Raises NotImplementedError if subclass has omitted a trigger classmethod.
        """
        self._log("%s diagnostic triggered." % self.trigger())
        return connection


class FinalizeAction(Action):

    def __init__(self):
        """
        The FinalizeAction is always added as the last Action in the top level pipeline by the parser.
        The tasks include finalising the connection (whatever is the last connection in the pipeline)
        and writing out the final pipeline structure containing the results as a logfile.
        """
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
        self.results = {'status': "Complete"}
        # FIXME: just write out a file, not put to stdout via logger.
        yaml_log = logging.getLogger("YAML")
        yaml_log.debug(yaml.dump(self.job.pipeline.describe()))
        # FIXME: detect a Cancel and set status as Cancel
        if self.job.pipeline.errors:
            self.results = {'status': "Incomplete"}
            yaml_log.debug("Status: Incomplete")
            yaml_log.debug(self.job.pipeline.errors)
        # from meliae import scanner
        # scanner.dump_all_objects('filename.json')


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

    @parameters.setter
    def parameters(self, data):
        self.__parameters__.update(data)

    @classmethod
    def accepts(cls, device, parameters):  # pylint: disable=unused-argument
        """
        Returns True if this deployment strategy can be used the the
        given device and details of an image in the parameters.

        Must be implemented by subclasses.
        """
        return NotImplementedError("accepts %s" % cls)

    @classmethod
    def select(cls, device, parameters):

        candidates = cls.__subclasses__()
        willing = [c for c in candidates if c.accepts(device, parameters)]

        if len(willing) == 0:
            raise NotImplementedError(
                "No deployment strategy available for the given "
                "device '%s'. %s" % (device.parameters['hostname'], cls))

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
        return NotImplementedError("accepts %s" % cls)

    @classmethod
    def select(cls, device, parameters):
        candidates = cls.__subclasses__()
        willing = [c for c in candidates if c.accepts(device, parameters)]
        if len(willing) == 0:
            raise NotImplementedError(
                "No boot strategy available for the device "
                "'%s' with the specified job parameters. %s" % (device.parameters['hostname'], cls)
            )

        # higher priority first
        compare = lambda x, y: cmp(y.priority, x.priority)
        prioritized = sorted(willing, compare)

        return prioritized[0]


class LavaTest(object):  # pylint: disable=abstract-class-not-used
    """
    Allows selection of the LAVA test method for this job within the parser.
    """

    priority = 1

    def __init__(self, parent):
        self.__parameters__ = {}
        self.pipeline = parent
        self.job = parent.job

    @contextmanager
    def test(self):
        """
        This method must be implemented by subclasses.
        """
        raise NotImplementedError("test %s" % self)

    @classmethod
    def accepts(cls, device, parameters):  # pylint: disable=unused-argument
        """
        Returns True if this Lava test strategy can be used on the
        given device and details of an image in the parameters.

        Must be implemented by subclasses.
        """
        return NotImplementedError("accepts %s" % cls)

    @classmethod
    def select(cls, device, parameters):
        candidates = cls.__subclasses__()
        willing = [c for c in candidates if c.accepts(device, parameters)]
        if len(willing) == 0:
            if hasattr(device, 'parameters'):
                msg = "No test strategy available for the device "\
                      "'%s' with the specified job parameters. %s" % (device.parameters['hostname'], cls)
            else:
                msg = "No test strategy available for the device. %s" % cls
            raise NotImplementedError(msg)

        # higher priority first
        compare = lambda x, y: cmp(y.priority, x.priority)
        prioritized = sorted(willing, compare)

        return prioritized[0]


class PipelineContext(object):
    """
    Replacement for the LavaContext which only holds data for the device for the
    current pipeline.

    The PipelineContext is the home for dynamic data generated by action run steps
    where that data is required by a later step. e.g. the mountpoint used by the
    loopback mount action will be needed by the umount action later.

    Data which does not change for the lifetime of the job must be kept as a
    parameter of the job, e.g. output_dir and target.

    Do NOT store data here which is not relevant to ALL pipelines, this is NOT
    the place for any configuration relating to devices or device types. The
    NewDevice class loads only the configuration required for the one device.

    Keep the memory footprint of this class as low as practical.
    """

    # FIXME: needs to pick up minimal general purpose config, e.g. proxy or cookies
    def __init__(self):
        self.pipeline_data = {}


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
