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
import sys
import copy
import time
import types
import signal
import datetime
import traceback
import subprocess
from collections import OrderedDict
from contextlib import contextmanager
from nose.tools import nottest

from lava_dispatcher.pipeline.log import YAMLLogger
from lava_dispatcher.pipeline.utils.constants import (
    ACTION_TIMEOUT,
    OVERRIDE_CLAMP_DURATION
)
from lava_dispatcher.pipeline.utils.strings import seconds_to_str

if sys.version > '3':
    from functools import reduce  # pylint: disable=redefined-builtin


class LAVAError(Exception):
    """ Base class for all exceptions in LAVA """
    error_code = 0
    error_help = ""
    error_type = ""


class InfrastructureError(LAVAError):
    """
    Exceptions based on an error raised by a component of the
    test which is neither the LAVA dispatcher code nor the
    code being executed on the device under test. This includes
    errors arising from the device (like the arndale SD controller
    issue) and errors arising from the hardware to which the device
    is connected (serial console connection, ethernet switches or
    internet connection beyond the control of the device under test).

    Use LAVABug for errors arising from bugs in LAVA code.
    """
    error_code = 1
    error_help = "InfrastructureError: The Infrastructure is not working " \
                 "correctly. Please report this error to LAVA admins."
    error_type = "Infrastructure"


class JobError(LAVAError):
    """
    An Error arising from the information supplied as part of the TestJob
    e.g. HTTP404 on a file to be downloaded as part of the preparation of
    the TestJob or a download which results in a file which tar or gzip
    does not recognise.
    """
    error_code = 2
    error_help = "JobError: Your job cannot terminate cleanly."
    error_type = "Job"


class LAVABug(LAVAError):
    """
    An error that is raised when an un-expected error is catched. Only happen
    when a bug is encountered.
    """
    error_code = 3
    error_help = "LAVABug: This is probably a bug in LAVA, please report it."
    error_type = "Bug"


class TestError(LAVAError):
    """
    An error in the operation of the test definition, e.g.
    in parsing measurements or commands which fail.
    Always ensure TestError is caught, logged and cleared. It is not fatal.
    """
    error_code = 4
    error_help = "TestError: A test failed to run, look at the error message."
    error_type = "Test"


class ConfigurationError(LAVAError):
    error_code = 5
    error_help = "ConfigurationError: The LAVA instance is not configured " \
                 "correctly. Please report this error to LAVA admins."
    error_type = "Configuration"


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
        self.actions = []
        self.parent = None
        self.parameters = {} if parameters is None else parameters
        self.job = job
        if parent is not None:
            # parent must be an Action
            if not isinstance(parent, Action):
                raise LAVABug("Internal pipelines need an Action as a parent")
            if not parent.level:
                raise LAVABug("Tried to create a pipeline using a parent action with no level set.")
            self.parent = parent

    def _check_action(self, action):  # pylint: disable=no-self-use
        if not action or not issubclass(type(action), Action):
            raise LAVABug("Only actions can be added to a pipeline: %s" % action)
        # if isinstance(action, DiagnosticAction):
        #     raise LAVABug("Diagnostic actions need to be triggered, not added to a pipeline.")
        if not action:
            raise LAVABug("Unable to add empty action to pipeline")

    def add_action(self, action, parameters=None):  # pylint: disable=too-many-branches
        self._check_action(action)
        self.actions.append(action)
        # FIXME: if this is only happening in unit test, this has to be fixed later on
        # should only be None inside the unit tests
        action.job = self.job
        if self.parent:  # action
            self.parent.pipeline = self
            action.level = "%s.%s" % (self.parent.level, len(self.actions))
            action.section = self.parent.section
        else:
            action.level = "%s" % (len(self.actions))

        # Use the pipeline parameters if the function was walled without
        # parameters.
        if parameters is None:
            parameters = self.parameters
        # if the action has an internal pipeline, initialise that here.
        action.populate(parameters)
        if 'default_connection_timeout' in parameters:
            # some action handlers do not need to pass all parameters to their children.
            action.connection_timeout.duration = parameters['default_connection_timeout']

        # Compute the timeout
        timeouts = []
        # FIXME: Only needed for the auto-tests
        if self.job is not None:
            if self.job.device is not None:
                # First, the device level overrides
                timeouts.append(self.job.device.get('timeouts', {}))
            # Then job level overrides
            timeouts.append(self.job.parameters.get('timeouts', {}))

        def dict_merge_get(dicts, key):
            value = None
            for d in dicts:
                value = d.get(key, value)
            return value

        def subdict_merge_get(dicts, key, subkey):
            value = None
            for d in dicts:
                value = d.get(key, {}).get(subkey, value)
            return value

        # Set the timeout. The order is:
        # 1/ the global action timeout
        # 2/ the individual action timeout
        # 3/ the action block timeout
        # pylint: disable=protected-access
        action._override_action_timeout(dict_merge_get(timeouts, 'action'))
        action._override_action_timeout(subdict_merge_get(timeouts, 'actions', action.name))
        action._override_action_timeout(parameters.get('timeout', None))

        action._override_connection_timeout(dict_merge_get(timeouts, 'connection'))
        action._override_connection_timeout(subdict_merge_get(timeouts, 'connections', action.name))

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
            raise JobError("Invalid job data: %s\n" % self.errors)

    def cleanup(self, connection):
        """
        Recurse through internal pipelines running action.cleanup(),
        in order of the pipeline levels.
        """
        for child in self.actions:
            child.cleanup(connection)

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
                raise LAVABug("No diagnosis for trigger %s" % complaint)
        self.job.triggers = []
        # Diagnosis is not allowed to alter the connection, do not use the return value.
        return None

    def run_actions(self, connection, max_end_time, args=None):  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        for action in self.actions:
            # Begin the action
            # TODO: this shouldn't be needed
            # The ci-test does not set the default logging class
            if isinstance(action.logger, YAMLLogger):
                action.logger.setMetadata(action.level, action.name)
            try:
                with action.timeout(max_end_time) as action_max_end_time:
                    # Add action start timestamp to the log message
                    # Log in INFO for root actions and in DEBUG for the other actions
                    timeout = seconds_to_str(action_max_end_time - action.timeout.start)
                    msg = 'start: %s %s (timeout %s)' % (action.level, action.name, timeout)
                    if self.parent is None:
                        action.logger.info(msg)
                    else:
                        action.logger.debug(msg)

                    new_connection = action.run(connection,
                                                action_max_end_time, args)
            except LAVAError as exc:
                exc_message = str(exc)
                action.errors = exc_message
                # set results including retries
                if "boot-result" not in action.data:
                    action.data['boot-result'] = 'failed'
                action.logger.error(exc_message)
                self._diagnose(connection)
                raise
            except Exception as exc:
                exc_message = str(exc)
                action.logger.exception(traceback.format_exc())
                action.errors = exc_message
                # Raise a LAVABug that will be correctly classified later
                raise LAVABug(exc_message)
            finally:
                # Add action end timestamp to the log message
                duration = round(action.timeout.elapsed_time)
                msg = "end: %s %s (duration %s)" % (action.level, action.name,
                                                    seconds_to_str(duration))
                if self.parent is None:
                    action.logger.info(msg)
                else:
                    action.logger.debug(msg)
                action.log_action_results()

            if new_connection:
                connection = new_connection
        return connection

    def prepare_actions(self):
        for action in self.actions:
            action.prepare()

    def post_process_actions(self):
        for action in self.actions:
            action.post_process()


class Action(object):  # pylint: disable=too-many-instance-attributes,too-many-public-methods

    def __init__(self):
        """
        Actions get added to pipelines by calling the
        Pipeline.add_action function. Other Action
        data comes from the parameters. Actions with
        internal pipelines push parameters to actions
        within those pipelines. Parameters are to be
        treated as inmutable.
        """
        # The level of this action within the pipeline. Levels start at one and
        # each pipeline within an command uses a level within the level of the
        # parent pipeline.
        # First command in Outer pipeline: 1
        # First command in pipeline within outer pipeline: 1.1
        # Level is set during pipeline creation and must not be changed
        # subsequently except by RetryCommand.
        self.level = None
        self.pipeline = None
        self.internal_pipeline = None
        self.__parameters__ = {}
        self.__errors__ = []
        self.job = None
        self.logger = logging.getLogger('dispatcher')
        self.__results__ = OrderedDict()
        self.timeout = Timeout(self.name)
        self.max_retries = 1  # unless the strategy or the job parameters change this, do not retry
        self.diagnostics = []
        self.protocols = []  # list of protocol objects supported by this action, full list in job.protocols
        self.section = None
        self.connection_timeout = Timeout(self.name)
        self.character_delay = 0
        self.force_prompt = False

    # public actions (i.e. those who can be referenced from a job file) must
    # declare a 'class-type' name so they can be looked up.
    # summary and description are used to identify instances.
    name = None
    # A short summary of this instance of a class inheriting from Action.  May
    # be None.
    summary = None
    # Used in the pipeline to explain what the commands will attempt to do.
    description = None

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
            raise LAVABug("Action parameters need to be a dictionary")

        # Set the timeout name now
        self.timeout.name = self.name
        # Overide the duration if needed
        if 'timeout' in self.parameters:
            # preserve existing overrides
            if self.timeout.duration == Timeout.default_duration():
                self.timeout.duration = Timeout.parse(self.parameters['timeout'])
        if 'connection_timeout' in self.parameters:
            self.connection_timeout.duration = Timeout.parse(self.parameters['connection_timeout'])

        # only unit tests should have actions without a pointer to the job.
        if 'failure_retry' in self.parameters and 'repeat' in self.parameters:
            self.errors = "Unable to use repeat and failure_retry, use a repeat block"
        if 'failure_retry' in self.parameters:
            self.max_retries = self.parameters['failure_retry']
        if 'repeat' in self.parameters:
            self.max_retries = self.parameters['repeat']
        if self.job:
            if self.job.device:
                if 'character_delays' in self.job.device:
                    self.character_delay = self.job.device['character_delays'].get(self.section, 0)

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
            raise LAVABug("Action results need to be a dictionary")

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
        # have already checked that self.name is not None, but pylint gets confused.
        if ' ' in self.name:  # pylint: disable=unsupported-membership-test
            self.errors = "Whitespace must not be used in action names, only descriptions or summaries: %s" % self.name

        if not self.summary:
            self.errors = "action %s (%s) lacks a summary" % (self.name, self)

        if not self.description:
            self.errors = "action %s (%s) lacks a description" % (self.name, self)

        if not self.section:
            self.errors = "%s action has no section set" % self

        # Collect errors from internal pipeline actions
        if self.internal_pipeline:
            self.internal_pipeline.validate_actions()

    def populate(self, parameters):
        """
        This method allows an action to add an internal pipeline.
        The parameters are used to configure the internal pipeline on the
        fly.
        """
        pass

    def run_command(self, command_list, allow_silent=False, allow_fail=False):  # pylint: disable=too-many-branches
        """
        Single location for all external command operations on the
        dispatcher, without using a shell and with full structured logging.
        Ensure that output for the YAML logger is a serialisable object
        and strip embedded newlines / whitespace where practical.
        Returns the output of the command (after logging the output)
        Includes default support for proxy settings in the environment.
        Blocks until the command returns then processes & logs the output.

        Caution: take care with the return value as this is highly dependent
        on the command_list and the expected results.

        :param: command_list - the command to run, with arguments
        :param: allow_silent - if True, the command may exit zero with no output
        without being considered to have failed.
        :return: On success (command exited zero), returns the command output.
        If allow_silent is True and the command produced no output, returns True.
        On failure (command exited non-zero), sets self.errors.
        If allow_silent is True, returns False, else returns the command output.
        """
        # FIXME: add option to only check stdout or stderr for failure output
        if not isinstance(command_list, list):
            raise LAVABug("commands to run_command need to be a list")
        log = None
        # nice is assumed to always exist (coreutils)
        command_list.insert(0, 'nice')
        self.logger.debug("%s", ' '.join(command_list))
        try:
            log = subprocess.check_output(command_list, stderr=subprocess.STDOUT)
            log = log.decode('utf-8')  # pylint: disable=redefined-variable-type
        except subprocess.CalledProcessError as exc:
            # the errors property doesn't support removing errors
            errors = []
            if sys.version > '3':
                if exc.output:
                    errors.append(exc.output.strip().decode('utf-8'))
                else:
                    errors.append(str(exc))
                msg = '[%s] command %s\nmessage %s\noutput %s\n' % (
                    self.name, [i.strip() for i in exc.cmd], str(exc), str(exc).split('\n'))
            else:
                if exc.output:
                    errors.append(exc.output.strip())
                elif exc.message:
                    errors.append(exc.message)
                else:
                    errors.append(str(exc))
                msg = "[%s] command %s\nmessage %s\noutput %s\nexit code %s" % (
                    self.name, [i.strip() for i in exc.cmd], [i.strip() for i in exc.message],
                    exc.output.split('\n'), exc.returncode)

            if exc.returncode != 0 and allow_fail:
                self.logger.info(msg)
                log = exc.output.strip()
            else:
                for error in errors:
                    self.errors = error
                self.logger.error(msg)

        # allow for commands which return no output
        if not log and allow_silent:
            return self.errors == []
        else:
            self.logger.debug('command output %s', log)
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
            if protocol.name not in self.parameters['protocols']:
                # nothing to do for this action with this protocol
                continue
            params = self.parameters['protocols'][protocol.name]
            for call_dict in [call for call in params if 'action' in call and call['action'] == self.name]:
                del call_dict['yaml_line']
                if 'message' in call_dict:
                    del call_dict['message']['yaml_line']
                if 'timeout' in call_dict:
                    del call_dict['timeout']['yaml_line']
                protocol.check_timeout(self.connection_timeout.duration, call_dict)
                self.logger.info("Making protocol call for %s using %s", self.name, protocol.name)
                reply = protocol(call_dict)
                message = protocol.collate(reply, call_dict)
                if message:
                    self.logger.info("Setting namespace data key %s to %s", message[0], message[1])
                    self.set_namespace_data(
                        action=protocol.name, label=protocol.name, key=message[0], value=message[1])

    def run(self, connection, max_end_time, args=None):
        """
        This method is responsible for performing the operations that an action
        is supposed to do.

        This method usually returns nothing. If it returns anything, that MUST
        be an instance of Connection. That connection will be the one passed on
        to the next action in the pipeline.

        In this classs this method does nothing. It must be implemented by
        subclasses

        :param connection: The Connection object to use to run the steps
        :param max_end_time: The maximum time before this action will timeout.
        :param args: Command and arguments to run
        :raise: Classes inheriting from BaseAction must handle
        all exceptions possible from the command and re-raise
        """
        self.call_protocols()
        if self.internal_pipeline:
            return self.internal_pipeline.run_actions(connection, max_end_time, args)
        if connection:
            connection.timeout = self.connection_timeout
        return connection

    def cleanup(self, connection):
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
        if self.internal_pipeline:
            self.internal_pipeline.cleanup(connection)

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
                'default_fixupdict', 'pattern',
                'parameters', 'SignalDirector', 'signal_director']):
            if attr == 'timeout':
                data['timeout'] = {'duration': self.timeout.duration, 'name': self.timeout.name}
            elif attr == 'connection_timeout':
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
            elif isinstance(getattr(self, attr), OrderedDict):
                data[attr] = dict(getattr(self, attr))
            else:
                data[attr] = getattr(self, attr)
        if 'deployment_data' in self.parameters:
            data['parameters'] = dict()
            data['parameters']['deployment_data'] = self.parameters['deployment_data'].__data__
        return data

    def get_namespace_data(self, action, label, key, deepcopy=True, parameters=None):  # pylint: disable=too-many-arguments
        """
        Get a namespaced data value from dynamic job data using the specified key.
        By default, returns a deep copy of the value instead of a reference to allow actions to
        manipulate lists and dicts based on common data without altering the values used by other actions.
        :param action: Name of the action which set the data or a commonly shared string used to
            correlate disparate actions
        :param label: Arbitrary label used by many actions to sub-divide similar keys with distinct
            values. Can be set to the same as the action.
        :param key: The lookup key for the requested value within the data defined by
            data[namespace][action][label]
        :param deepcopy: If deepcopy is False, the reference is used - meaning that certain operations on the
            namespaced data values other than simple strings will be able to modify the data without calls to
            set_namespace_data.
        :param parameters: Pass parameters when calling get_namespace_data from populate() as the parameters
            will not have been set in the action at that point.
        """
        params = parameters if parameters else self.parameters
        namespace = params.get('namespace', 'common')
        value = self.data.get(namespace, {}).get(action, {}).get(label, {}).get(key, None)  # pylint: disable=no-member
        if value is None:
            return None
        return copy.deepcopy(value) if deepcopy else value

    def set_namespace_data(self, action, label, key, value, parameters=None):  # pylint: disable=too-many-arguments
        """
        Storage for filenames (on dispatcher or on device) and other common data (like labels and ID strings)
        which are set in one Action and used in one or more other Actions elsewhere in the same pipeline.
        :param action: Name of the action which set the data or a commonly shared string used to
            correlate disparate actions
        :param label: Arbitrary label used by many actions to sub-divide similar keys with distinct
            values. Can be set to the same as the action.
        :param key: The lookup key for the requested value within the data defined by
            data[namespace][action][label]
        :param value: The value to set into the namespace data, can be an object.
        :param parameters: Pass parameters when calling get_namespace_data from populate() as the parameters
            will not have been set in the action at that point.
        """
        params = parameters if parameters else self.parameters
        namespace = params.get('namespace', 'common')
        if not label or not key:
            self.errors = "Invalid call to set_namespace_data: %s" % action
        self.data.setdefault(namespace, {})  # pylint: disable=no-member
        self.data[namespace].setdefault(action, {})
        self.data[namespace][action].setdefault(label, {})
        self.data[namespace][action][label][key] = value

    def wait(self, connection, max_end_time=None):
        if not connection:
            return
        if not connection.connected:
            self.logger.debug("Already disconnected")
            return
        if not max_end_time:
            max_end_time = self.timeout.duration + self.timeout.start
        remaining = max_end_time - time.time()
        # FIXME: connection.prompt_str needs to be always a list
        # bootloader_prompt is one which does not get set that way
        # also need functionality to clear the list at times.
        self.logger.debug("%s: Wait for prompt %s (timeout %s)",
                          self.name, connection.prompt_str, seconds_to_str(remaining))
        if self.force_prompt:
            return connection.force_prompt_wait(remaining)
        else:
            return connection.wait(max_end_time)

    def mkdtemp(self, override=None):
        return self.job.mkdtemp(self.name, override=override)

    def _override_action_timeout(self, timeout):
        """
        Only to be called by the Pipeline object, add_action().
        """
        if timeout is None:
            return
        if not isinstance(timeout, dict):
            raise JobError("Invalid timeout %s" % str(timeout))
        self.timeout = Timeout(self.name, Timeout.parse(timeout))

    def _override_connection_timeout(self, timeout):
        """
        Only to be called by the Pipeline object, add_action().
        """
        if timeout is None:
            return
        if not isinstance(timeout, dict):
            raise JobError("Invalid connection timeout %s" % str(timeout))
        self.connection_timeout = Timeout(self.name, Timeout.parse(timeout))

    def log_action_results(self):
        if self.results and isinstance(self.logger, YAMLLogger):
            self.logger.results({  # pylint: disable=no-member
                "definition": "lava",
                "case": self.name,
                "level": self.level,
                "duration": "%.02f" % self.timeout.elapsed_time,
                "result": "fail" if self.errors else "pass",
                "extra": self.results})
            self.results.update(
                {
                    'level': self.level,
                    'duration': self.timeout.elapsed_time,
                    'timeout': self.timeout.duration,
                    'connection-timeout': self.connection_timeout.duration
                }
            )

    @nottest
    def test_needs_deployment(self, parameters):  # pylint: disable=no-self-use
        needs_deployment = False
        if parameters['namespace'] in parameters['test_info']:
            testclasses = parameters['test_info'][parameters['namespace']]
            for testclass in testclasses:
                if testclass['class'].needs_deployment_data():
                    needs_deployment = True
        return needs_deployment

    @nottest
    def test_has_shell(self, parameters):  # pylint: disable=no-self-use
        has_shell = False
        if parameters['namespace'] in parameters['test_info']:
            testclasses = parameters['test_info'][parameters['namespace']]
            for testclass in testclasses:
                if testclass['class'].has_shell():
                    has_shell = True
        return has_shell

    @nottest
    def test_needs_overlay(self, parameters):  # pylint: disable=no-self-use
        needs_overlay = False
        if parameters['namespace'] in parameters['test_info']:
            testclasses = parameters['test_info'][parameters['namespace']]
            for testclass in testclasses:
                if testclass['class'].needs_overlay():
                    needs_overlay = True
        return needs_overlay


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
        self.start = 0
        self.elapsed_time = -1
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
        if not isinstance(data, dict):
            raise ConfigurationError("Invalid timeout data")
        duration = datetime.timedelta(days=data.get('days', 0),
                                      hours=data.get('hours', 0),
                                      minutes=data.get('minutes', 0),
                                      seconds=data.get('seconds', 0))
        if not duration:
            return Timeout.default_duration()
        return int(duration.total_seconds())

    def _timed_out(self, signum, frame):  # pylint: disable=unused-argument
        duration = int(time.time() - self.start)
        raise JobError("%s timed out after %s seconds" % (self.name, duration))

    @contextmanager
    def __call__(self, action_max_end_time=None):
        self.start = time.time()
        if action_max_end_time is None:
            # action_max_end_time is None when cleaning the pipeline after a
            # timeout.
            # In this case, the job timeout is not taken into account.
            max_end_time = self.start + self.duration
        else:
            max_end_time = min(action_max_end_time, self.start + self.duration)

        duration = int(max_end_time - self.start)
        if duration <= 0:
            # If duration is lower than 0, then the timeout should be raised now.
            # Calling signal.alarm in this case will only deactivate the alarm
            # (by passing 0 or the unsigned value).
            self._timed_out(None, None)

        signal.signal(signal.SIGALRM, self._timed_out)
        signal.alarm(duration)

        try:
            yield max_end_time
        except:
            raise
        finally:
            # clear the timeout alarm, the action has returned
            signal.alarm(0)
            self.elapsed_time = time.time() - self.start

    def modify(self, duration):
        """
        Called from the parser if the job YAML wants to set an override on a per-action
        timeout. Complete job timeouts can be larger than the clamp.
        """
        if self.protected:
            raise JobError("Trying to modify a protected timeout: %s.", self.name)
        self.duration = max(min(OVERRIDE_CLAMP_DURATION, duration), 1)  # FIXME: needs support in /etc/


def action_namespaces(parameters=None):
    """Iterates through the job parameters to identify all the action
    namespaces."""
    namespaces = set()
    for action in parameters['actions']:
        for name in action:
            if isinstance(action[name], dict):
                if action[name].get('namespace', None):
                    namespaces.add(action[name].get('namespace', None))
    return namespaces
