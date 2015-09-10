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
import os
import sys
import copy
import time
import types
import signal
import datetime
import subprocess
from collections import OrderedDict
from contextlib import contextmanager

from lava_dispatcher.pipeline.log import YAMLLogger
from lava_dispatcher.pipeline.utils.constants import OVERRIDE_CLAMP_DURATION, ACTION_TIMEOUT

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
    Always ensure TestError is caught, logged and cleared. It is not fatal.
    """
    pass


class InternalObject(object):  # pylint: disable=too-few-public-methods
    """
    An object within the dispatcher pipeline which should not be included in
    the description of the pipeline.
    """
    pass


class Pipeline(object):  # pylint: disable=too-many-instance-attributes
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
        self.job = job
        self.branch_level = 1  # the level of the last added child
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

    def _check_action(self, action):  # pylint: disable=no-self-use
        if not action or not issubclass(type(action), Action):
            raise RuntimeError("Only actions can be added to a pipeline: %s" % action)
        # if isinstance(action, DiagnosticAction):
        #     raise RuntimeError("Diagnostic actions need to be triggered, not added to a pipeline.")
        if not action:
            raise RuntimeError("Unable to add empty action to pipeline")

    def add_action(self, action, parameters=None):
        self._check_action(action)
        self.actions.append(action)
        action.level = "%s.%s" % (self.branch_level, len(self.actions))
        # FIXME: if this is only happening in unit test, this has to be fixed later on
        if self.job:  # should only be None inside the unit tests
            action.job = self.job
        if self.parent:  # action
            self.children[self] = self.actions
            self.parent.pipeline = self
            action.section = self.parent.section
        else:
            action.level = "%s" % (len(self.actions))
        # create a log handler just for this action.
        if self.job and self.job.parameters['output_dir']:
            log_level_dir = action.level.split('.')[0]
            yaml_filename = os.path.join(
                self.job.parameters['output_dir'], log_level_dir,
                "%s-%s.log" % (action.level, action.name)
            )
            if not os.path.exists(os.path.dirname(yaml_filename)):
                os.makedirs(os.path.dirname(yaml_filename))
            action.log_filename = yaml_filename

        # Use the pipeline parameters if the function was walled without
        # parameters.
        if parameters is None:
            parameters = self.parameters
        # if the action has an internal pipeline, initialise that here.
        action.populate(parameters)
        # Set the timeout
        # FIXME: only the last test is really useful. The first ones are only
        # needed to run the tests that do not use a device and job.
        if self.job is not None and \
           self.job.device is not None and \
           action.name in self.job.device.get('timeouts', {}):
            action.timeout = Timeout(
                action.name,
                Timeout.parse(
                    self.job.device['timeouts'][action.name]
                )
            )
        # Set the parameters after populate so the sub-actions are also
        # getting the parameters.
        # Also set the parameters after the creation of the default timeout
        # so timeouts specified in the job override the defaults.
        # job overrides device timeouts:
        # FIXME: this shouldn't be needed once the device configuration is generated using the job definition
        if self.job and 'timeouts' in self.job.parameters and action.name in self.job.parameters['timeouts']:
            parameters['timeout'] = self.job.parameters['timeouts'][action.name]

        action.parameters = parameters

    def describe(self, verbose=True):
        """
        Describe the current pipeline, recursing through any
        internal pipelines.
        :return: a recursive dictionary
        """
        desc = []
        for action in self.actions:
            if verbose:
                current = action.explode()
            else:
                cls = str(type(action))[8:-2].replace('lava_dispatcher.pipeline.', '')
                current = {'class': cls, 'name': action.name}
            if action.pipeline is not None:
                current['pipeline'] = action.pipeline.describe(verbose)
            desc.append(current)
        return desc

    @property
    def errors(self):
        sub_action_errors = [a.errors for a in self.actions]
        if not sub_action_errors:  # allow for jobs with no actions
            return []
        return reduce(lambda a, b: a + b, sub_action_errors)

    def validate_actions(self):
        for action in self.actions:
            action.validate()

        # If this is the root pipeline, raise the errors
        if self.parent is None and self.errors:
            raise JobError("Invalid job data: %s\n" % '\n'.join(self.errors))

    def pipeline_cleanup(self):
        """
        Recurse through internal pipelines running action.cleanup(),
        in order of the pipeline levels.
        """
        for child in self.actions:
            child.cleanup()
            if child.internal_pipeline:
                child.internal_pipeline.pipeline_cleanup()

    def cleanup_actions(self, connection, message):
        if not self.job.pipeline:
            # is this only unit-tests doing this?
            return
        for child in self.job.pipeline.actions:
            if child.internal_pipeline:
                child.internal_pipeline.pipeline_cleanup()
        # exit out of the pipeline & run the Finalize action to close the connection and poweroff the device
        for child in self.job.pipeline.actions:
            # rely on the action name here - use isinstance if pipeline moves into a dedicated module.
            if child.name == 'finalize':
                child.errors = message
                child.run(connection, None)

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

    def run_actions(self, connection, args=None):  # pylint: disable=too-many-branches,too-many-statements,too-many-locals

        def cancelling_handler(*args):  # pylint: disable=unused-argument
            """
            Catches KeyboardInterrupt or SIGTERM from anywhere below the top level
            pipeline and allow cleanup actions to happen on all actions,
            not just the ones directly related to the currently running action.
            """
            self.cleanup_actions(None, "Cancelled")
            signal.signal(signal.SIGINT, signal.default_int_handler)
            raise KeyboardInterrupt

        timeout_start = time.time()
        for action in self.actions:
            if self.job and self.job.timeout and time.time() > timeout_start + self.job.timeout.duration:
                # affects all pipelines, including internal
                # the action which overran the timeout has been allowed to complete.
                name = self.job.parameters.get('job_name', '?')
                msg = "Job '%s' timed out after %s seconds" % (name, int(self.job.timeout.duration))
                action.errors = msg
                final = self.actions[-1]
                if final.name == "finalize":
                    final.run(connection, None)
                else:
                    msg = "Invalid job pipeline - no finalize action to run after job timeout."
                    action.logger.error(msg)
                    raise RuntimeError(msg)
                raise JobError(msg)

            # Begin the action
            # TODO: this shouldn't be needed
            # The ci-test does not set the default logging class
            if isinstance(action.logger, YAMLLogger):
                action.logger.setMetadata(action.level, action.name)
            # Add action start timestamp to the log message
            msg = {'msg': 'start: %s %s (max %ds)' % (action.level,
                                                      action.name,
                                                      action.timeout.duration),
                   'ts': datetime.datetime.utcnow().isoformat()}
            if self.parent is None:
                action.logger.info(msg)
            else:
                action.logger.debug(msg)
            try:
                if not self.parent:
                    signal.signal(signal.SIGINT, cancelling_handler)
                    signal.signal(signal.SIGTERM, cancelling_handler)
                start = time.time()
                new_connection = None
                try:
                    # FIXME: not sure to understand why we have two cases here?
                    if not connection:
                        with action.timeout.action_timeout():
                            new_connection = action.run(connection, args)
                    else:
                        new_connection = action.run(connection, args)
                # overly broad exceptions will cause issues with RetryActions
                # always ensure the unit tests continue to pass with changes here.
                except (ValueError, KeyError, TypeError, RuntimeError, AttributeError) as exc:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback_details = {
                        'filename': exc_traceback.tb_frame.f_code.co_filename,
                        'lineno': exc_traceback.tb_lineno,
                        'name': exc_traceback.tb_frame.f_code.co_name,
                        'type': exc_type.__name__,
                        'message': exc_value.message,
                    }
                    action.logger.exception(traceback_details)
                    raise RuntimeError(exc)
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                action.elapsed_time = time.time() - start
                # Add action end timestamp to the log message
                msg = {'msg': "%s duration: %.02f" % (action.name,
                                                      action.elapsed_time),
                       'ts': datetime.datetime.utcnow().isoformat()}
                if self.parent is None:
                    action.logger.info(msg)
                else:
                    action.logger.debug(msg)
                if action.results and isinstance(action.logger, YAMLLogger):
                    action.results.update(
                        {
                            'level': action.level,
                            'duration': action.elapsed_time,
                            'timeout': action.timeout.duration,
                        }
                    )
                    action.logger.results({action.name: action.results})
                if new_connection:
                    connection = new_connection
            except KeyboardInterrupt:
                self.cleanup_actions(connection, "Cancelled")
                sys.exit(1)
            except (JobError, InfrastructureError) as exc:
                action.errors = exc.message
                # set results including retries
                action.results = {"fail": exc}
                self._diagnose(connection)
                action.cleanup()
                self.cleanup_actions(connection, exc.message)
                raise exc
        return connection

    def prepare_actions(self):
        for action in self.actions:
            action.prepare()

    def post_process_actions(self):
        for action in self.actions:
            action.post_process()


class Action(object):  # pylint: disable=too-many-instance-attributes

    def __init__(self):
        """
        Actions get added to pipelines by calling the
        Pipeline.add_action function. Other Action
        data comes from the parameters. Actions with
        internal pipelines push parameters to actions
        within those pipelines. Parameters are to be
        treated as inmutable.
        """
        self.__summary__ = None
        self.__description__ = None
        self.__level__ = None
        self.pipeline = None
        self.internal_pipeline = None
        self.__parameters__ = {}
        self.__errors__ = []
        self.elapsed_time = None
        self.log_filename = None
        self.job = None
        self.logger = logging.getLogger('dispatcher')
        self.__results__ = OrderedDict()
        self.timeout = Timeout(self.name)
        self.max_retries = 1  # unless the strategy or the job parameters change this, do not retry
        self.diagnostics = []
        self.protocols = []  # list of protocol objects supported by this action, full list in job.protocols
        self.section = None

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

    @classmethod
    def select(cls, name):
        for subclass in cls.__subclasses__():  # pylint: disable=no-member
            if subclass.name == name:
                return subclass
        raise JobError("Cannot find action named \"%s\"" % name)

    @property
    def errors(self):
        if self.internal_pipeline:
            return self.__errors__ + self.internal_pipeline.errors
        else:
            return self.__errors__

    @errors.setter
    def errors(self, error):
        if error:
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

        # Set the timeout name now
        self.timeout.name = self.name
        # Overide the duration if needed
        if 'timeout' in self.parameters:
            self.timeout.duration = Timeout.parse(self.parameters['timeout'])

        # only unit tests should have actions without a pointer to the job.
        if 'failure_retry' in self.parameters and 'repeat' in self.parameters:
            self.errors = "Unable to use repeat and failure_retry, use a repeat block"
        if 'failure_retry' in self.parameters:
            self.max_retries = self.parameters['failure_retry']
        if 'repeat' in self.parameters:
            self.max_retries = self.parameters['repeat']

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
        # Basic checks
        if not self.name:
            self.errors = "%s action has no name set" % self
        if ' ' in self.name:
            self.errors = "Whitespace must not be used in action names, only descriptions or summaries: %s" % self.name

        if not self.section:
            self.errors = "%s action has no section set" % self

        # Collect errors from internal pipeline actions
        self.job.context.setdefault(self.name, {})
        if self.internal_pipeline:
            self.internal_pipeline.validate_actions()
            self.errors.extend(self.internal_pipeline.errors)  # pylint: disable=maybe-no-member

    def populate(self, parameters):
        """
        This method allows an action to add an internal pipeline.
        The parameters are used to configure the internal pipeline on the
        fly.
        """
        pass

    def run_command(self, command_list):
        """
        Single location for all external command operations on the
        dispatcher, without using a shell and with full structured logging.
        Ensure that output for the YAML logger is a serialisable object
        and strip embedded newlines / whitespace where practical.
        Returns the output of the command (after logging the output)
        Includes default support for proxy settings in the environment.
        Blocks until the command returns then processes & logs the output.
        """
        # FIXME: add option to only check stdout or stderr for failure output
        if type(command_list) != list:
            raise RuntimeError("commands to run_command need to be a list")
        log = None
        command_list.insert(0, 'nice')
        try:
            log = subprocess.check_output(command_list, stderr=subprocess.STDOUT)
        except OSError as exc:
            self.logger.exception({exc.strerror: exc.child_traceback.split('\n')})
        except subprocess.CalledProcessError as exc:
            self.errors = exc.output.strip() if not exc.message else exc.message
            self.logger.exception({
                'command': [i.strip() for i in exc.cmd],
                'message': [i.strip() for i in exc.message],
                'output': exc.output.split('\n')})

        # allow for commands which return no output
        if not log:
            self.logger.debug({'command': command_list})
            return ''
        else:
            self.logger.debug({'command': command_list,
                               'output': log})
            return log

    def call_protocols(self):
        """
        Actions which support using protocol calls from the job submission use this routine to execute those calls.
        It is up to the action to determine when the protocols are called within the run step of that action.
        The order in which calls are made for any one action is not guaranteed.
        The reply is set in the context data.
        Although actions may have multiple protocol calls in individual tests, use of multiple calls in Strategies
        needs to be avoided to ensure that the individual calls can be easily reused and identified.
        """
        if 'protocols' not in self.parameters:
            return
        for protocol in self.job.protocols:
            for params in self.parameters['protocols'][protocol.name]:
                for call in [
                        params for name in params
                        if name == 'action' and params[name] == self.name]:
                    reply = protocol(call)
                    message = protocol.collate(reply, params)
                    self.logger.debug(
                        "Setting common data key %s to %s"
                        % (message[0], message[1]))
                    self.set_common_data(protocol.name, message[0], message[1])

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
        """
        self.call_protocols()
        if self.internal_pipeline:
            return self.internal_pipeline.run_actions(connection, args)
        if connection:
            connection.timeout = self.timeout
        return connection

    def cleanup(self):
        """
        cleanup will *only* be called after run() if run() raises an exception.
        Use cleanup with any resources that may be left open by an interrupt or failed operation
        such as, but not limited to:

            - open file descriptors
            - mount points
            - error codes

        Use contextmanagers or signal handlers to clean up any resources when there are no errors,
        instead of using cleanup().
        """
        pass

    def explode(self):
        """
        serialisation support
        Omit our objects marked as internal by inheriting form InternalObject instead of object,
        e.g. SignalMatch
        """
        data = {}
        attrs = set([attr for attr in dir(self)
                     if not attr.startswith('_') and getattr(self, attr) and not
                     isinstance(getattr(self, attr), types.MethodType) and not
                     isinstance(getattr(self, attr), InternalObject)])

        # noinspection PySetFunctionToLiteral
        for attr in attrs - set([
                'internal_pipeline', 'job', 'logger', 'pipeline',
                'parameters', 'SignalDirector', 'signal_director']):
            if attr == 'timeout':
                data['timeout'] = {'duration': self.timeout.duration, 'name': self.timeout.name}
            elif attr == 'url':
                data['url'] = self.url.geturl()  # pylint: disable=no-member
            elif attr == 'vcs':
                data[attr] = getattr(self, attr).url
            elif attr == 'protocols':
                data['protocols'] = {}
                for protocol in getattr(self, attr):
                    data['protocols'][protocol.name] = {}
                    protocol_attrs = set([attr for attr in dir(protocol)
                                          if not attr.startswith('_') and getattr(protocol, attr) and not
                                          isinstance(getattr(protocol, attr), types.MethodType) and not
                                          isinstance(getattr(protocol, attr), InternalObject)])
                    for protocol_attr in protocol_attrs:
                        if protocol_attr not in ['logger']:
                            data['protocols'][protocol.name][protocol_attr] = getattr(protocol, protocol_attr)
            else:
                data[attr] = getattr(self, attr)
        if 'deployment_data' in self.parameters:
            data['parameters'] = dict()
            data['parameters']['deployment_data'] = self.parameters['deployment_data'].__data__
        return data

    def get_common_data(self, ns, key, deepcopy=True):  # pylint: disable=invalid-name
        """
        Get a common data value from the specified namespace using the specified key.
        By default, returns a deep copy of the value instead of a reference to allow actions to
        manipulate lists and dicts based on common data without altering the values used by other actions.
        If deepcopy is False, the reference is used - meaning that certain operations on common data
        values other than simple strings will be able to modify the common data without calls to set_common_data.
        """
        if ns not in self.data['common']:
            return None
        value = self.data['common'][ns].get(key, None)
        return copy.deepcopy(value) if deepcopy else value

    def set_common_data(self, ns, key, value):  # pylint: disable=invalid-name
        """
        Storage for filenames (on dispatcher or on device) and other common data (like labels and ID strings)
        which are set in one Action and used in one or more other Actions elsewhere in the same pipeline.
        """
        # ensure the key exists
        self.data['common'].setdefault(ns, {})
        self.data['common'][ns][key] = value

    def wait(self, connection):
        if not connection:
            return
        if not connection.connected:
            self.logger.debug("Already disconnected")
            return
        self.logger.debug("%s: Wait for prompt. %s seconds" % (self.name, int(self.timeout.duration)))
        connection.wait()


class Timeout(object):
    """
    The Timeout class is a declarative base which any actions can use. If an Action has
    a timeout, that timeout name and the duration will be output as part of the action
    description and the timeout is then exposed as a modifiable value via the device_type,
    device or even job inputs. (Some timeouts may be deemed "protected" which may not be
    altered by the job. All timeouts are subject to a hardcoded maximum duration which
    cannot be exceeded by device_type, device or job input, only by the Action initialising
    the timeout.
    If a connection is set, this timeout is used per pexpect operation on that connection.
    If a connection is not set, this timeout applies for the entire run function of the action.
    """
    def __init__(self, name, duration=ACTION_TIMEOUT, protected=False):
        self.name = name
        self.duration = duration  # Actions can set timeouts higher than the clamp.
        self.protected = protected

    @classmethod
    def default_duration(cls):
        return ACTION_TIMEOUT

    @classmethod
    def parse(cls, data):
        """
        Parsed timeouts can be set in device configuration or device_type configuration
        and can therefore exceed the clamp.
        """
        if type(data) is not dict:
            raise RuntimeError("Invalid timeout data")
        days = 0
        hours = 0
        minutes = 0
        seconds = 0
        if 'days' in data:
            days = data['days']
        if 'hours' in data:
            hours = data['hours']
        if 'minutes' in data:
            minutes = data['minutes']
        if 'seconds' in data:
            seconds = data['seconds']
        duration = datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        if not duration:
            return Timeout.default_duration()
        return duration.total_seconds()

    def _timed_out(self, signum, frame):  # pylint: disable=unused-argument
        raise JobError("%s timed out after %s seconds" % (self.name, int(self.duration)))

    @contextmanager
    def action_timeout(self):
        signal.signal(signal.SIGALRM, self._timed_out)
        signal.alarm(int(self.duration))
        yield
        # clear the timeout alarm, the action has returned
        signal.alarm(0)

    def modify(self, duration):
        """
        Called from the parser if the job YAML wants to set an override on a per-action
        timeout. Complete job timeouts can be larger than the clamp.
        """
        if self.protected:
            raise JobError("Trying to modify a protected timeout: %s.", self.name)
        self.duration = max(min(OVERRIDE_CLAMP_DURATION, duration), 1)  # FIXME: needs support in /etc/
