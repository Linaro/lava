# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from contextlib import suppress as suppress_exc
from typing import TYPE_CHECKING

from lava_common.constants import (
    DISTINCTIVE_PROMPT_CHARACTERS,
    LINE_SEPARATOR,
    LOGIN_INCORRECT_MSG,
    LOGIN_TIMED_OUT_MSG,
)
from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.connections.ssh import SShSession
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.utils.messages import LinuxKernelMessages

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class LoginAction(Action):
    name = "login-action"
    description = "Real login action."
    summary = "Login after boot."

    check_prompt_characters_warning = (
        "The string '%s' does not look like a typical prompt and"
        " could match status messages instead. Please check the"
        " job log files and use a prompt string which matches the"
        " actual prompt string more closely."
    )

    def __init__(self, job: Job):
        super().__init__(job)
        self.force_prompt = True  # Kernel logs may overlap with login prompt on boot

    def check_kernel_messages(
        self, connection, max_end_time, fail_msg, auto_login=False
    ):
        """
        Use the additional pexpect expressions to detect warnings
        and errors during the kernel boot. Ensure all test jobs using
        auto-login-action have a result set so that the duration is
        always available when the action completes successfully.
        """
        if isinstance(connection, SShSession):
            self.logger.debug("Skipping kernel messages")
            return
        if self.parameters.get("ignore_kernel_messages", False):
            self.logger.debug("Skipping kernel messages. Flag set to false")
            if self.force_prompt:
                connection.force_prompt_wait(max_end_time)
            else:
                connection.wait(max_end_time)
            return
        self.logger.info("Parsing kernel messages")
        self.logger.debug(connection.prompt_str)
        parsed = LinuxKernelMessages.parse_failures(
            connection,
            self,
            max_end_time=max_end_time,
            fail_msg=fail_msg,
            auto_login=auto_login,
        )
        if len(parsed) and "success" in parsed[0]:
            self.results = {"success": parsed[0]["success"]}
            if len(parsed) > 1:
                # errors detected.
                self.logger.warning("Kernel warnings or errors detected.")
                self.results = {"extra": parsed}
        elif not parsed:
            self.results = {"success": "No kernel warnings or errors detected."}
        else:
            self.results = {"fail": parsed}
            self.logger.warning("Kernel warnings or errors detected.")

    def _check_prompt_characters(self, chk_prompt: str | type) -> None:
        if not isinstance(chk_prompt, str):
            return

        if not any(c in chk_prompt for c in DISTINCTIVE_PROMPT_CHARACTERS):
            self.logger.warning(self.check_prompt_characters_warning, chk_prompt)

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not connection:
            return connection
        prompts = self.parameters.get("prompts")
        for prompt in prompts:
            self._check_prompt_characters(prompt)

        connection.prompt_str = []
        if not self.parameters.get("ignore_kernel_messages", False):
            connection.prompt_str = LinuxKernelMessages.get_init_prompts()
        connection.prompt_str.extend(prompts)

        # Needs to be added after the standard kernel message matches
        # FIXME: check behaviour if boot_message is defined too.
        failure = self.parameters.get("failure_message")
        if failure:
            self.logger.info("Checking for user specified failure message: %s", failure)
            connection.prompt_str.append(failure)

        # linesep should come from deployment_data as from now on it is OS dependent
        linesep = self.get_namespace_data(
            action="deploy-device-env", label="environment", key="line_separator"
        )
        connection.raw_connection.linesep = linesep if linesep else LINE_SEPARATOR
        self.logger.debug(
            "Using line separator: #%r#", connection.raw_connection.linesep
        )

        # Skip auto login if the configuration is not found
        params = self.parameters.get("auto_login")
        if not params:
            self.logger.debug("No login prompt set.")
            # If auto_login is not enabled, login will time out if login
            # details are requested.
            connection.prompt_str.append(LOGIN_TIMED_OUT_MSG)
            connection.prompt_str.append(LOGIN_INCORRECT_MSG)
            # wait for a prompt or kernel messages
            self.check_kernel_messages(connection, max_end_time, failure)
            if "success" in self.results:
                check = self.results["success"]
                if LOGIN_TIMED_OUT_MSG in check or LOGIN_INCORRECT_MSG in check:
                    raise JobError(
                        "auto_login not enabled but image requested login details."
                    )
            # clear kernel message prompt patterns
            connection.prompt_str = list(self.parameters.get("prompts", []))
            # already matched one of the prompts
        else:
            self.logger.info("Waiting for the login prompt")
            connection.prompt_str.append(params["login_prompt"])
            connection.prompt_str.append(LOGIN_INCORRECT_MSG)

            # wait for a prompt or kernel messages
            self.check_kernel_messages(
                connection, max_end_time, failure, auto_login=True
            )
            if "success" in self.results:
                if LOGIN_INCORRECT_MSG in self.results["success"]:
                    self.logger.warning(
                        "Login incorrect message matched before the login prompt. "
                        "Please check that the login prompt is correct. "
                        "Retrying login..."
                    )
            self.logger.debug("Sending username %s", params["username"])
            connection.sendline(params["username"], delay=self.character_delay)
            # clear the kernel_messages patterns
            connection.prompt_str = list(self.parameters.get("prompts", []))

            if "password_prompt" in params:
                self.logger.info("Waiting for password prompt")
                connection.prompt_str.append(params["password_prompt"])
                # This can happen if password_prompt is misspelled.
                connection.prompt_str.append(LOGIN_TIMED_OUT_MSG)

                # wait for the password prompt
                index = self.wait(connection, max_end_time)
                if index:
                    self.logger.debug(
                        "Matched prompt #%s: %s", index, connection.prompt_str[index]
                    )
                    if connection.prompt_str[index] == LOGIN_TIMED_OUT_MSG:
                        raise JobError(
                            "Password prompt not matched, please update the job "
                            "definition with the correct one."
                        )
                self.logger.debug("Sending password %s", params["password"])
                connection.sendline(params["password"], delay=self.character_delay)
                # clear the Password pattern
                connection.prompt_str = list(self.parameters.get("prompts", []))

            connection.prompt_str.append(LOGIN_INCORRECT_MSG)
            connection.prompt_str.append(LOGIN_TIMED_OUT_MSG)
            # wait for the login process to provide the prompt
            index = self.wait(connection, max_end_time)
            if index:
                self.logger.debug("Matched %s %s", index, connection.prompt_str[index])
                if connection.prompt_str[index] == LOGIN_INCORRECT_MSG:
                    raise JobError(LOGIN_INCORRECT_MSG)
                if connection.prompt_str[index] == LOGIN_TIMED_OUT_MSG:
                    raise JobError(LOGIN_TIMED_OUT_MSG)

            # clear the login patterns
            connection.prompt_str = list(self.parameters.get("prompts", []))

            login_commands = params.get("login_commands")
            if login_commands is not None:
                self.logger.debug("Running login commands")
                for command in login_commands:
                    connection.sendline(command, delay=self.character_delay)
                    connection.wait()

        return connection


class AutoLoginAction(RetryAction):
    """
    Automatically login on the device.
    If 'auto_login' is not present in the parameters, this action does nothing.

    This Action expect POSIX-compatible support of PS1 from shell
    """

    name = "auto-login-action"
    description = (
        "automatically login after boot using job parameters and checking for messages."
    )
    summary = "Auto-login after boot with support for kernel messages."

    def __init__(self, job: Job, booting=True):
        super().__init__(job)
        self.params = None
        self.booting = booting  # if a boot is expected, False for second UART or ssh.

    def validate(self):
        super().validate()
        # Skip auto login if the configuration is not found
        self.method = self.parameters["method"]
        params = self.parameters.get("auto_login")
        if params:
            if not isinstance(params, dict):
                self.errors = "'auto_login' should be a dictionary"
                return

            if "login_prompt" not in params:
                self.errors = "'login_prompt' is mandatory for auto_login"
            elif not params["login_prompt"]:
                self.errors = "Value for 'login_prompt' cannot be empty"

            if "username" not in params:
                self.errors = "'username' is mandatory for auto_login"

            if "password_prompt" in params:
                if "password" not in params:
                    self.errors = (
                        "'password' is mandatory if 'password_prompt' is "
                        "used in auto_login"
                    )

            if "login_commands" in params:
                login_commands = params["login_commands"]
                if not isinstance(login_commands, list):
                    self.errors = "'login_commands' must be a list"
                if not login_commands:
                    self.errors = "'login_commands' must not be empty"

        prompts = self.parameters.get("prompts")
        if prompts is None:
            self.errors = "'prompts' is mandatory for AutoLoginAction"

        if not isinstance(prompts, (list, str)):
            self.errors = "'prompts' should be a list or a str"

        if not prompts:
            self.errors = "Value for 'prompts' cannot be empty"

        if isinstance(prompts, list):
            for prompt in prompts:
                if not prompt:
                    self.errors = "Items of 'prompts' can't be empty"

        methods = self.job.device["actions"]["boot"]["methods"]
        with suppress_exc(KeyError, TypeError):
            if "parameters" in methods[self.method]:
                # fastboot devices usually lack method parameters
                self.params = methods[self.method]["parameters"]

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(LoginAction(self.job))

    def run(self, connection, max_end_time):
        # Prompts commonly include # - when logging such strings,
        # use lazy logging or the string will not be quoted correctly.
        if self.booting:
            kernel_start_message = self.parameters.get("parameters", {}).get(
                "kernel-start-message",
                self.job.device.get_constant("kernel-start-message"),
            )
            if kernel_start_message:
                connection.prompt_str = [kernel_start_message]

            if self.params and self.params.get("boot_message"):
                self.logger.warning(
                    "boot_message is being deprecated in favour of "
                    "kernel-start-message in constants"
                )
                connection.prompt_str = [self.params.get("boot_message")]

            error_messages = self.job.device.get_constant(
                "error-messages", prefix=self.method, missing_ok=True
            )
            if error_messages:
                if isinstance(connection.prompt_str, str):
                    connection.prompt_str = [connection.prompt_str]
                connection.prompt_str = connection.prompt_str + error_messages
            if kernel_start_message:
                res = self.wait(connection)
                if res != 0:
                    msg = "matched a bootloader error message: '%s' (%d)" % (
                        connection.prompt_str[res],
                        res,
                    )
                    raise InfrastructureError(msg)

        connection = super().run(connection, max_end_time)
        return connection

    @staticmethod
    def params_have_prompts(parameters: dict) -> bool:
        return "prompts" in parameters
