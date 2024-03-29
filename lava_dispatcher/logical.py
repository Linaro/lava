# Copyright (C) 2014,2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from lava_common.exceptions import (
    ConfigurationError,
    InfrastructureError,
    JobError,
    LAVABug,
    TestError,
)
from lava_dispatcher.action import Action
from lava_dispatcher.utils.strings import seconds_to_str

if TYPE_CHECKING:
    from typing import Optional


class RetryAction(Action):
    """
    RetryAction support failure_retry and repeat.
    failure_retry returns upon the first success.
    repeat continues the loop whether there is a failure or not.
    Only the top level Boot and Test actions support 'repeat' as this is set in the job.
    """

    def __init__(self):
        super().__init__()
        self.sleep = 1

    def validate(self):
        """
        The reasoning here is that the RetryAction should be in charge of an internal pipeline
        so that the retry logic only occurs once and applies equally to the entire pipeline
        of the retry.
        """
        super().validate()
        if not self.pipeline:
            raise LAVABug(
                "Retry action %s needs to implement an internal pipeline" % self.name
            )

    def run(self, connection, max_end_time):
        self.sleep = self.parameters.get("failure_retry_interval", self.sleep)
        parent_end_time = max_end_time

        retries = 0
        has_failed_exc: Optional[Exception] = None
        has_parent_timed_out = False
        self.call_protocols()
        while retries < self.max_retries:
            retries += 1
            try:
                connection = self.pipeline.run_actions(connection, max_end_time)
                if "repeat" not in self.parameters:
                    # failure_retry returns on first success. repeat returns only at max_retries.
                    return connection
            # Do not retry for LAVABug (as it's a bug in LAVA)
            except (InfrastructureError, JobError, TestError) as exc:
                has_failed_exc = exc
                # Print the error message
                self.logger.error(
                    "%s failed: %d of %d attempts. '%s'",
                    self.name,
                    retries,
                    self.max_retries,
                    exc,
                )
                # Cleanup the action to allow for a safe restart
                self.cleanup(connection)

                # re-raise if this is the last loop
                if retries == self.max_retries:
                    self.errors = "%s retries failed for %s" % (retries, self.name)
                    raise

                # Stop retrying if parent timed out
                if time.monotonic() >= parent_end_time:
                    has_parent_timed_out = True
                    break

                # Wait some time before retrying
                time.sleep(self.sleep)
                # Restart max_end_time or the retry on a timeout fails with duration < 0
                current_time = time.monotonic()
                max_end_time += current_time - self.timeout.start
                self.timeout.start = current_time
                self.logger.warning(
                    "Retrying: %s %s (timeout %s)",
                    self.level,
                    self.name,
                    seconds_to_str(max_end_time - self.timeout.start),
                )

        # If we are repeating, check that all repeat were a success.
        if has_failed_exc:
            # tried and failed
            exception_text = (
                f"{retries} retries out of "
                f"{self.max_retries} failed for {self.name}"
            )
            if has_parent_timed_out:
                exception_text = (
                    f"No time left for remaining {self.max_retries - retries} retries. "
                ) + exception_text
            # Use the same exception class as the last failed
            # run exception.
            retry_fail_exc = type(has_failed_exc)(exception_text)
            raise retry_fail_exc from has_failed_exc
        return connection


class Deployment:
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
    section = "deploy"

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
    def accepts(cls, device, parameters):
        """
        Returns True if this deployment strategy can be used by the
        given device and details of an image in the parameters.

        Must be implemented by subclasses.
        """
        return NotImplementedError("accepts %s" % cls)

    @classmethod
    def deploy_check(cls, device, parameters):
        if not device:
            raise JobError('job "device" was None')
        if "actions" not in device:
            raise ConfigurationError(
                'Invalid device configuration, no "actions" in device configuration'
            )
        if "to" not in parameters:
            raise ConfigurationError('"to" not specified in deploy parameters')
        if "deploy" not in device["actions"]:
            raise ConfigurationError(
                '"deploy" is not in the device configuration actions'
            )
        if "methods" not in device["actions"]["deploy"]:
            raise ConfigurationError(
                'Device misconfiguration, no "methods" in device configuration deploy actions'
            )

    @classmethod
    def uses_deployment_data(cls):
        return True

    @classmethod
    def select(cls, device, parameters):
        cls.deploy_check(device, parameters)
        candidates = cls.__subclasses__()
        replies = {}
        willing = []
        for c in candidates:
            res = c.accepts(device, parameters)
            if not isinstance(res, tuple):
                raise LAVABug(
                    "class %s accept function did not return a tuple" % c.__name__
                )
            if res[0]:
                willing.append(c)
            else:
                replies[c.name] = res[1]

        if not willing:
            replies_string = ""
            for name, reply in replies.items():
                replies_string += "%s: %s\n" % (name, reply)
            raise JobError(
                "None of the deployment strategies accepted your deployment parameters, reasons given:\n%s"
                % replies_string
            )

        willing.sort(key=lambda x: x.priority, reverse=True)
        return willing[0]


class Boot:
    """
    Allows selection of the boot method for this job within the parser.
    """

    priority = 0
    section = "boot"

    @classmethod
    def boot_check(cls, device, parameters):
        if not device:
            raise JobError('job "device" was None')
        if "method" not in parameters:
            raise ConfigurationError("method not specified in boot parameters")
        if "actions" not in device:
            raise ConfigurationError(
                'Invalid device configuration, no "actions" in device configuration'
            )
        if "boot" not in device["actions"]:
            raise ConfigurationError(
                '"boot" is not in the device configuration actions'
            )
        if "methods" not in device["actions"]["boot"]:
            raise ConfigurationError(
                'Device misconfiguration, no "methods" in device configuration boot action'
            )

    @classmethod
    def accepts(cls, device, parameters):
        """
        Returns True if this deployment strategy can be used by the
        given device and details of an image in the parameters.

        Must be implemented by subclasses.
        """
        return NotImplementedError("accepts %s" % cls)

    @classmethod
    def select(cls, device, parameters):
        cls.boot_check(device, parameters)
        candidates = cls.__subclasses__()
        replies = {}
        willing = []
        for c in candidates:
            res = c.accepts(device, parameters)
            if not isinstance(res, tuple):
                raise LAVABug(
                    "class %s accept function did not return a tuple" % c.__name__
                )
            if res[0]:
                willing.append(c)
            else:
                class_name = c.name if hasattr(c, "name") else c.__name__
                replies[class_name] = res[1]

        if not willing:
            replies_string = ""
            for name, reply in replies.items():
                replies_string += "%s: %s\n" % (name, reply)
            raise JobError(
                "None of the boot strategies accepted your boot parameters, reasons given:\n%s"
                % replies_string
            )

        willing.sort(key=lambda x: x.priority, reverse=True)
        return willing[0]


class LavaTest:
    """
    Allows selection of the LAVA test method for this job within the parser.
    """

    priority = 1
    section = "test"

    @classmethod
    def accepts(cls, device, parameters):
        """
        Returns True if this Lava test strategy can be used on the
        given device and details of an image in the parameters.

        Must be implemented by subclasses.
        """
        return NotImplementedError("accepts %s" % cls)

    @classmethod
    def select(cls, device, parameters):
        candidates = cls.__subclasses__()
        replies = {}
        willing = []
        for c in candidates:
            res = c.accepts(device, parameters)
            if not isinstance(res, tuple):
                raise LAVABug(
                    "class %s accept function did not return a tuple" % c.__name__
                )
            if res[0]:
                willing.append(c)
            else:
                class_name = c.name if hasattr(c, "name") else c.__name__
                replies[class_name] = res[1]

        if not willing:
            replies_string = ""
            for name, reply in replies.items():
                replies_string += "%s: %s\n" % (name, reply)
            raise JobError(
                "None of the test strategies accepted your test parameters, reasons given:\n%s"
                % replies_string
            )

        willing.sort(key=lambda x: x.priority, reverse=True)
        return willing[0]

    @classmethod
    def needs_deployment_data(cls):
        return NotImplementedError("needs_deployment_data %s" % cls)

    @classmethod
    def needs_overlay(cls):
        return NotImplementedError("needs_overlay %s" % cls)

    @classmethod
    def has_shell(cls):
        return NotImplementedError("has_shell %s" % cls)


class PipelineContext:
    """
    Replacement for the LavaContext which only holds data for the device for the
    current pipeline.

    The PipelineContext is the home for dynamic data generated by action run steps
    where that data is required by a later step. e.g. the mountpoint used by the
    loopback mount action will be needed by the umount action later.

    Data which does not change for the lifetime of the job must be kept as a
    parameter of the job, e.g. dispatcher_config and target.

    Do NOT store data here which is not relevant to ALL pipelines, this is NOT
    the place for any configuration relating to devices or device types. The
    NewDevice class loads only the configuration required for the one device.

    Keep the memory footprint of this class as low as practical.

    If a particular piece of data is used in multiple places, use the 'common'
    area to avoid all classes needing to know which class populated the data.
    """

    # FIXME: needs to pick up minimal general purpose config, e.g. proxy or cookies
    def __init__(self):
        self.pipeline_data = {}
