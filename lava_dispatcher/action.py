# Copyright (C) 2014-2019 Linaro Limited
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

from collections import OrderedDict
import logging
import copy
from functools import reduce
import pexpect
import time
import types
import traceback
import shlex
import subprocess  # nosec - internal
import warnings

from lava_common.decorators import nottest
from lava_common.timeout import Timeout
from lava_common.exceptions import (
    LAVABug,
    LAVAError,
    JobError,
    TestError,
    LAVATimeoutError,
)
from lava_common.log import YAMLLogger
from lava_dispatcher.utils.strings import seconds_to_str


class InternalObject:
    """
    An object within the dispatcher pipeline which should not be included in
    the description of the pipeline.
    """

    pass


class Pipeline:
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
                raise LAVABug(
                    "Tried to create a pipeline using a parent action with no level set."
                )
            self.parent = parent

    def _check_action(self, action):
        if not action:
            raise LAVABug("Need an action to add to the pipeline, not None.")
        elif not issubclass(type(action), Action):
            raise LAVABug("Only actions can be added to a pipeline: %s" % action)
        # if isinstance(action, DiagnosticAction):
        #     raise LAVABug("Diagnostic actions need to be triggered, not added to a pipeline.")

    def add_action(self, action, parameters=None):
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

        # Compute the timeout
        timeouts = []
        # FIXME: Only needed for the auto-tests
        if self.job is not None:
            if self.job.device is not None:
                # First, the device level overrides
                timeouts.append(self.job.device.get("timeouts", {}))
            # Then job level overrides
            timeouts.append(self.job.parameters.get("timeouts", {}))

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

        action._override_action_timeout(dict_merge_get(timeouts, "action"))
        action._override_action_timeout(
            subdict_merge_get(timeouts, "actions", action.name)
        )
        action._override_action_timeout(parameters.get("timeout"))

        action._override_connection_timeout(dict_merge_get(timeouts, "connection"))
        action._override_connection_timeout(
            subdict_merge_get(timeouts, "connections", action.name)
        )

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
                cls = str(type(action))[8:-2].replace("lava_dispatcher.", "")
                current = {"class": cls, "name": action.name}
            if action.pipeline is not None:
                sub_desc = action.pipeline.describe(verbose)
                if sub_desc:
                    current["pipeline"] = sub_desc
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
            try:
                action.validate()
            except JobError as exc:
                action.errors = "%s %s: %s" % (action.level, action.name, str(exc))

        # If this is the root pipeline, raise the errors
        if self.parent is None and self.errors:
            raise JobError("Invalid job data: %s\n" % self.errors)

    def cleanup(self, connection):
        """
        Recurse through internal pipelines running action.cleanup(),
        in order of the pipeline levels.
        """
        for child in self.actions:
            try:
                child.cleanup(connection)
            except Exception as exc:
                # Just log the exception and continue the cleanup
                child.logger.error(
                    "Failed to clean after action '%s': %s", child.name, str(exc)
                )
                child.logger.exception(traceback.format_exc())

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

    def run_actions(self, connection, max_end_time):
        for action in self.actions:
            failed = False
            namespace = action.parameters.get("namespace", "common")
            # Begin the action
            try:
                parent = self.parent if self.parent else self.job
                with action.timeout(parent, max_end_time) as action_max_end_time:
                    # Add action start timestamp to the log message
                    # Log in INFO for root actions and in DEBUG for the other actions
                    timeout = seconds_to_str(action_max_end_time - action.timeout.start)
                    msg = "start: %s %s (timeout %s) [%s]" % (
                        action.level,
                        action.name,
                        timeout,
                        namespace,
                    )
                    if self.parent is None:
                        action.logger.info(msg)
                    else:
                        action.logger.debug(msg)

                    new_connection = action.run(connection, action_max_end_time)
            except LAVATimeoutError as exc:
                action.logger.exception(str(exc))
                # allows retries without setting errors, which make the job incomplete.
                failed = True
                action.results = {"fail": str(exc)}
                if action.timeout.can_skip(action.parameters):
                    if self.parent is None:
                        action.logger.warning(
                            "skip_timeout is set for %s - continuing to next action block."
                            % (action.name)
                        )
                    else:
                        raise
                    new_connection = None
                else:
                    raise TestError(str(exc))
            except LAVAError as exc:
                action.logger.exception(str(exc))
                # allows retries without setting errors, which make the job incomplete.
                failed = True
                action.results = {"fail": str(exc)}
                self._diagnose(connection)
                raise
            except Exception as exc:
                action.logger.exception(traceback.format_exc())
                # allows retries without setting errors, which make the job incomplete.
                failed = True
                action.results = {"fail": str(exc)}
                # Raise a LAVABug that will be correctly classified later
                raise LAVABug(str(exc))
            finally:
                # Add action end timestamp to the log message
                duration = round(action.timeout.elapsed_time)
                msg = "end: %s %s (duration %s) [%s]" % (
                    action.level,
                    action.name,
                    seconds_to_str(duration),
                    namespace,
                )
                if self.parent is None:
                    action.logger.info(msg)
                else:
                    action.logger.debug(msg)
                # set results including retries and failed actions
                action.log_action_results(fail=failed)

            if new_connection:
                connection = new_connection
        return connection


class CommandLogger:
    """
    Grab output of a command line tool and stream it to the logger
    """

    def __init__(self, logger):
        self.line = ""
        self.logger = logger

    def write(self, new_line):
        lines = self.line + new_line

        # Print one full line at a time. A partial line is kept in memory.
        if "\n" in lines:
            last_ret = lines.rindex("\n")
            self.line = lines[last_ret + 1 :]
            lines = lines[:last_ret]
            for line in lines.split("\n"):
                self.logger.debug(">> %s", line)
        else:
            self.line = lines

    def flush(self, force=False):
        if force and self.line:
            self.write("\n")


class Action:
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
        self.__parameters__ = {}
        self.__errors__ = []
        self.job = None
        self.logger = logging.getLogger("dispatcher")
        self.__results__ = {}
        self.timeout = Timeout(self.name, exception=self.timeout_exception)
        # unless the strategy or the job parameters change this, do not retry
        self.max_retries = 1
        self.diagnostics = []
        # list of protocol objects supported by this action, full list in job.protocols
        self.protocols = []
        self.connection_timeout = Timeout(self.name, exception=self.timeout_exception)
        self.character_delay = 0
        self.force_prompt = False

    # Section
    section = None
    # public actions (i.e. those who can be referenced from a job file) must
    # declare a 'class-type' name so they can be looked up.
    # summary and description are used to identify instances.
    name = None
    # Used in the pipeline to explain what the commands will attempt to do.
    description = None
    # A short summary of this instance of a class inheriting from Action.  May
    # be None.
    summary = None
    # Exception to raise when this action is timing out
    timeout_exception = JobError
    # Exception to raise when a command run by the action fails
    command_exception = JobError

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
        for subclass in cls.__subclasses__():
            if subclass.name == name:
                return subclass
        raise JobError('Cannot find action named "%s"' % name)

    @property
    def errors(self):
        if self.pipeline:
            return self.__errors__ + self.pipeline.errors
        else:
            return self.__errors__

    @errors.setter
    def errors(self, error):
        if error:
            self.__errors__.append(error)

    @property
    def valid(self):
        return not bool([x for x in self.errors if x])

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

        # Override the duration if needed
        if "timeout" in self.parameters:
            # preserve existing overrides
            if self.timeout.duration == Timeout.default_duration():
                self.timeout.duration = Timeout.parse(self.parameters["timeout"])
        if "connection_timeout" in self.parameters:
            self.connection_timeout.duration = Timeout.parse(
                self.parameters["connection_timeout"]
            )

        # only unit tests should have actions without a pointer to the job.
        if "failure_retry" in self.parameters and "repeat" in self.parameters:
            raise JobError("Unable to use repeat and failure_retry, use a repeat block")
        if "failure_retry" in self.parameters:
            self.max_retries = self.parameters["failure_retry"]
        else:
            if self.job:
                if self.job.device and type(self.job.device).__name__ != "dict":
                    if "constants" in self.job.device:
                        max_retry = self.get_constant("failure_retry", "")
                        if max_retry:
                            self.max_retries = int(max_retry)
                            # In case of a boot section, used boot_retry if it exists
                            boot_retry = self.get_constant("boot_retry", "")
                            if self.section == "boot" and boot_retry:
                                self.max_retries = int(boot_retry)
        if "repeat" in self.parameters:
            self.max_retries = self.parameters["repeat"]
        if self.job:
            if self.job.device:
                if "character_delays" in self.job.device:
                    self.character_delay = self.job.device["character_delays"].get(
                        self.section, 0
                    )

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

    def get_constant(self, key, prefix):
        # whilst deployment data is still supported, check if the key exists there.
        # once deployment_data is removed, merge with device.get_constant
        if self.parameters.get("deployment_data"):
            if key in self.parameters["deployment_data"]:
                return self.parameters["deployment_data"][key]
        return self.job.device.get_constant(key, prefix=prefix)

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
        if " " in self.name:
            self.errors = (
                "Whitespace must not be used in action names, only descriptions or summaries: %s"
                % self.name
            )

        if "_" in self.name:
            self.errors = "Use - instead of _ in action names: %s" % self.name

        if not self.summary:
            self.errors = "action %s (%s) lacks a summary" % (self.name, self)

        if not self.description:
            self.errors = "action %s (%s) lacks a description" % (self.name, self)

        if not self.section:
            self.errors = "action %s (%s) has no section set" % (self.name, self)

        # Collect errors from internal pipeline actions
        if self.pipeline:
            self.pipeline.validate_actions()

    def populate(self, parameters):
        """
        This method allows an action to add an internal pipeline.
        The parameters are used to configure the internal pipeline on the
        fly.
        """
        pass

    def parsed_command(self, command_list, allow_fail=False, cwd=None):
        """
        Support for external command operations on the dispatcher with output handling,
        without using a shell and with full structured logging.
        Ensure that output for the YAML logger is a serialisable object
        and strip embedded newlines / whitespace where practical.
        Returns the output of the command (after logging the output)
        Includes default support for proxy settings in the environment.
        Blocks until the command returns then processes & logs the output.

        Note: logs the returncode in all circumstances as a result in the lava test suite.

        :param: command_list - the command to run, with arguments
        :param: allow_fail - if True, the command may exist non-zero without
        being considered to have failed. Use to determine the kind of error
        by checking the output or in Finalize.
        :return: On success (command exited zero), returns the command output.
        On failure (command exited non-zero and allow_fail not set)
          sets self.errors and raises self.command_exception
        """
        if not isinstance(command_list, list):
            raise LAVABug("commands to parsed_command need to be a list")
        log = ""
        command_list = [str(s) for s in command_list]
        self.logger.debug("%s", " ".join(command_list))
        try:
            log = subprocess.check_output(  # nosec - internal
                command_list, stderr=subprocess.STDOUT, cwd=cwd
            )
            log = log.decode("utf-8", errors="replace")
            if allow_fail:
                self.results = {"returncode": "0"}
                self.results = {"output_len": len(log)}
                self.logger.info(
                    "Parsed command exited zero with allow_fail set, returning %s bytes."
                    % len(log)
                )
        except subprocess.CalledProcessError as exc:
            # the errors property doesn't support removing errors
            errors = []
            retcode = exc.returncode
            if exc.output:
                output = exc.output.strip().decode("utf-8", errors="replace")
            else:
                output = str(exc)
            errors.append(output)
            self.results = {"returncode": "%s" % exc.returncode}
            self.logger.info("Parsed command exited %s." % retcode)
            base = (
                "action: {0}\ncommand: {1}\nmessage: {2}\noutput: {3}\nreturn code: {4}"
            )
            msg = base.format(
                self.name,
                [i.strip() for i in exc.cmd],
                str(exc),
                "\n".join(errors),
                retcode,
            )
            self.results = {"output": output}

            # the exception is raised due to a non-zero exc.returncode
            if allow_fail:
                self.logger.info(msg)
                log = exc.output.strip().decode("utf-8", errors="replace")
            else:
                for error in errors:
                    self.errors = error
                self.logger.error(msg)
                # if not allow_fail, fail the command with the specified exception.
                raise self.command_exception(exc) from exc

        for line in log.split("\n"):
            self.logger.debug("output: %s", line)
        return log

    def run_cmd(
        self, command_list, allow_fail=False, error_msg=None, exception=None, cwd=None
    ):
        """
        Run the given command on the dispatcher. If the command fail, a
        JobError will be raised unless allow_fail is set to True.
        The command output will be visible (almost) in real time.

        :param: command_list - the command to run (as a list)
        :param: allow_fail - if True, do not raise a JobError when the command fail (return non 0)
        :param: error_msg - the exception message.
        :param: exception - the exception to raise.
        :param: cwd - the current working directory for this command
        :return: return code of the command
        """
        # Build the command list (adding 'nice' at the front)
        if isinstance(command_list, str):
            command_list = shlex.split(command_list)
        elif not isinstance(command_list, list):
            raise LAVABug("commands to run_cmd need to be a list or a string")
        command_list = [str(s) for s in command_list]

        # Default to self.command_exception
        command_exception = (
            exception if exception is not None else self.command_exception
        )

        # Build the error message
        log_error_msg = "Unable to run 'nice' '%s'" % "' '".join(command_list)
        if error_msg is None:
            error_msg = log_error_msg

        # Start the subprocess
        self.logger.debug("Calling: 'nice' '%s'", "' '".join(command_list))
        start = time.time()

        cmd_logger = CommandLogger(self.logger)
        ret = None
        try:
            proc = pexpect.spawn(
                "nice",
                command_list,
                cwd=cwd,
                encoding="utf-8",
                codec_errors="replace",
                logfile=cmd_logger,
                timeout=self.timeout.duration,
                searchwindowsize=10,
            )
            proc.expect(pexpect.EOF)
            # wait for the process and record the return value
            ret = proc.wait()
        except pexpect.TIMEOUT:
            self.logger.error("Timed out after %s seconds", int(time.time() - start))
            proc.terminate()
            proc.wait()
        except pexpect.ExceptionPexpect as exc:
            self.logger.error("Unable to run: %s", exc)

        cmd_logger.flush(force=True)
        if ret is not None:
            self.logger.debug(
                "Returned %d in %s seconds", ret, int(time.time() - start)
            )
        else:
            self.logger.debug("Failed in %s seconds", int(time.time() - start))

        # Check the return value
        if ret != 0 and not allow_fail:
            self.logger.error("Unable to run 'nice' '%s'", command_list)
            raise command_exception(error_msg)
        return ret

    def run_command(self, command_list, allow_silent=False, allow_fail=False, cwd=None):
        """
        Deprecated - use run_cmd or parsed_command instead.

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
        warnings.warn("run_command should be replaced by run_cmd", DeprecationWarning)

        # FIXME: add option to only check stdout or stderr for failure output
        if not isinstance(command_list, list):
            raise LAVABug("commands to run_command need to be a list")
        log = None
        command_list = [str(s) for s in command_list]
        self.logger.debug("%s", " ".join(command_list))
        try:
            log = subprocess.check_output(  # nosec - managed
                command_list, stderr=subprocess.STDOUT, cwd=cwd
            )
            log = log.decode("utf-8", errors="replace")
        except subprocess.CalledProcessError as exc:
            # the errors property doesn't support removing errors
            errors = []
            if exc.output:
                errors.append(exc.output.strip().decode("utf-8", errors="replace"))
            else:
                errors.append(str(exc))
            msg = "action: %s\ncommand: %s\nmessage: %s\noutput: %s\n" % (
                self.name,
                [i.strip() for i in exc.cmd],
                str(exc),
                "\n".join(errors),
            )

            # the exception is raised due to a non-zero exc.returncode
            if allow_fail:
                self.logger.info(msg)
                log = exc.output.strip().decode("utf-8", errors="replace")
            else:
                for error in errors:
                    self.errors = error
                self.logger.error(msg)
                # if not allow_fail, fail the command
                return False

        # allow for commands which return no output
        if not log and allow_silent:
            return self.errors == []
        else:
            for line in log.split("\n"):
                self.logger.debug("output: %s", line)
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
        if "protocols" not in self.parameters:
            return
        for protocol in self.job.protocols:
            if protocol.name not in self.parameters["protocols"]:
                # nothing to do for this action with this protocol
                continue
            params = self.parameters["protocols"][protocol.name]
            names = [
                call
                for call in params
                if "action" in call and call["action"] == self.name
            ]
            for call_dict in names:
                protocol.check_timeout(self.connection_timeout.duration, call_dict)
                self.logger.info(
                    "Making protocol call for %s using %s", self.name, protocol.name
                )
                reply = protocol(call_dict, action=self)
                message = protocol.collate(reply, call_dict)
                if message:
                    self.logger.info(
                        "Setting namespace data key %s to %s", message[0], message[1]
                    )
                    self.set_namespace_data(
                        action=protocol.name,
                        label=protocol.name,
                        key=message[0],
                        value=message[1],
                    )

    def run(self, connection, max_end_time):
        """
        This method is responsible for performing the operations that an action
        is supposed to do.

        This method usually returns nothing. If it returns anything, that MUST
        be an instance of Connection. That connection will be the one passed on
        to the next action in the pipeline.

        In this class this method does nothing. It must be implemented by
        subclasses

        :param connection: The Connection object to use to run the steps
        :param max_end_time: The maximum time before this action will timeout.
        :raise: Classes inheriting from BaseAction must handle
        all exceptions possible from the command and re-raise
        """
        self.call_protocols()
        if self.pipeline:
            return self.pipeline.run_actions(connection, max_end_time)
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
        if self.pipeline:
            self.pipeline.cleanup(connection)

    def explode(self):
        """
        serialisation support
        Omit our objects marked as internal by inheriting form InternalObject instead of object,
        e.g. SignalMatch
        """
        data = {}
        attrs = set(
            (
                attr
                for attr in dir(self)
                if not attr.startswith("_")
                and getattr(self, attr)
                and not isinstance(getattr(self, attr), types.MethodType)
                and not isinstance(getattr(self, attr), InternalObject)
            )
        )

        # noinspection PySetFunctionToLiteral
        skip_set = set(
            [
                "pipeline",
                "job",
                "logger",
                "pipeline",
                "default_fixupdict",
                "pattern",
                "parameters",
                "SignalDirector",
                "signal_director",
            ]
        )
        for attr in attrs - skip_set:
            if attr == "timeout":
                data["timeout"] = {
                    "duration": self.timeout.duration,
                    "name": self.timeout.name,
                }
            elif attr == "connection_timeout":
                data["timeout"] = {
                    "duration": self.timeout.duration,
                    "name": self.timeout.name,
                }
            elif attr == "url":
                data["url"] = self.url.geturl()
            elif attr == "vcs":
                data[attr] = getattr(self, attr).url
            elif attr == "protocols":
                data["protocols"] = {}
                for protocol in getattr(self, attr):
                    data["protocols"][protocol.name] = {}
                    protocol_attrs = set(
                        (
                            attr
                            for attr in dir(protocol)
                            if not attr.startswith("_")
                            and getattr(protocol, attr)
                            and not isinstance(
                                getattr(protocol, attr), types.MethodType
                            )
                            and not isinstance(getattr(protocol, attr), InternalObject)
                        )
                    )
                    for protocol_attr in protocol_attrs:
                        if protocol_attr not in ["logger"]:
                            data["protocols"][protocol.name][protocol_attr] = getattr(
                                protocol, protocol_attr
                            )
            elif isinstance(getattr(self, attr), OrderedDict):
                data[attr] = dict(getattr(self, attr))
            else:
                data[attr] = getattr(self, attr)
        return data

    def get_namespace_keys(self, action, parameters=None):
        """ Return the keys for the given action """
        params = parameters if parameters else self.parameters
        namespace = params["namespace"]
        return self.data.get(namespace, {}).get(action, {}).keys()

    def get_namespace_data(self, action, label, key, deepcopy=True, parameters=None):
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
        namespace = params["namespace"]
        value = self.data.get(namespace, {}).get(action, {}).get(label, {}).get(key)
        if value is None:
            return None
        return copy.deepcopy(value) if deepcopy else value

    def set_namespace_data(self, action, label, key, value, parameters=None):
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
        namespace = params["namespace"]
        if not label or not key:
            raise LAVABug("Invalid call to set_namespace_data: %s" % action)
        self.data.setdefault(namespace, {})
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
        self.logger.debug(
            "%s: Wait for prompt %s (timeout %s)",
            self.name,
            connection.prompt_str,
            seconds_to_str(remaining),
        )
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
        self.timeout.duration = Timeout.parse(timeout)
        if self.timeout.duration > self.job.timeout.duration:
            self.logger.warning("Action timeout for %s exceeds Job timeout", self.name)

    def _override_connection_timeout(self, timeout):
        """
        Only to be called by the Pipeline object, add_action().
        """
        if timeout is None:
            return
        if not isinstance(timeout, dict):
            raise JobError("Invalid connection timeout %s" % str(timeout))
        self.connection_timeout.duration = Timeout.parse(timeout)

    def log_action_results(self, fail=False):
        if self.results and isinstance(self.logger, YAMLLogger):
            res = "pass"
            if self.errors:
                res = "fail"
            if fail:
                # allows retries without setting errors, which make the job incomplete.
                res = "fail"
            self.logger.results(
                {
                    "definition": "lava",
                    "namespace": self.parameters.get("namespace", "common"),
                    "case": self.name,
                    "level": self.level,
                    "duration": "%.02f" % self.timeout.elapsed_time,
                    "result": res,
                    "extra": self.results,
                }
            )
            self.results.update(
                {
                    "duration": self.timeout.elapsed_time,
                    "timeout": self.timeout.duration,
                    "connection-timeout": self.connection_timeout.duration,
                }
            )

    @nottest
    def test_needs_deployment(self, parameters):
        ns = parameters["namespace"]
        for info in self.job.test_info.get(ns, []):
            if info["class"].needs_deployment_data(info["parameters"]):
                return True
        return False

    @nottest
    def test_has_shell(self, parameters):
        ns = parameters["namespace"]
        for info in self.job.test_info.get(ns, []):
            if info["class"].has_shell(info["parameters"]):
                return True
        return False

    @nottest
    def test_needs_overlay(self, parameters):
        ns = parameters["namespace"]
        for info in self.job.test_info.get(ns, []):
            if info["class"].needs_overlay(info["parameters"]):
                return True
        return False
