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


import time
from contextlib import contextmanager
from lava_dispatcher.pipeline.action import (
    Action,
    JobError,
    InfrastructureError,
    TestError,
)


class RetryAction(Action):
    """
    RetryAction support failure_retry and repeat.
    failure_retry returns upon the first success.
    repeat continues the loop whether there is a failure or not.
    Only the top level Boot and Test actions support 'repeat' as this is set in the job.
    """

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
                if 'repeat' not in self.parameters:
                    # failure_retry returns on first success. repeat returns only at max_retries.
                    return new_connection
            except (JobError, InfrastructureError, TestError) as exc:
                self.retries += 1
                self.errors = "%s failed: %d of %d attempts. '%s'" % (self.name, self.retries, self.max_retries, exc)
                if self.timeout:
                    self.logger.warning(" %s: timeout. %s seconds" % (self.timeout.name, int(self.timeout.duration)))
                time.sleep(self.sleep)
        if not self.valid:
            self.errors = "%s retries failed for %s" % (self.retries, self.name)
        return connection

    # FIXME: needed?
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
        self.section = 'diagnostic'
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
        self.logger.debug("%s diagnostic triggered." % self.trigger())
        return connection


class AdjuvantAction(Action):  # pylint: disable=abstract-class-not-used
    """
    Adjuvants are associative actions - partners and helpers which can be executed if
    the initial Action determines a particular state.
    Distinct from DiagnosticActions, Adjuvants execute within the normal flow of the
    pipeline but support being skipped if the functionality is not required.
    The default is that the Adjuvant is omitted. i.e. Requiring an adjuvant is an
    indication that the device did not perform entirely as could be expected. One
    example is when a soft reboot command fails, an Adjuvant can cause a power cycle
    via the PDU.
    """
    def __init__(self):
        super(AdjuvantAction, self).__init__()
        self.adjuvant = False

    @classmethod
    def key(cls):
        raise NotImplementedError("Base class has no key")

    def validate(self):
        super(AdjuvantAction, self).validate()
        try:
            self.key()
        except NotImplementedError:
            self.errors = "Adjuvant action without a key: %s" % self.name

    def run(self, connection, args=None):
        if not connection:
            raise RuntimeError("Called %s without an active Connection" % self.name)
        if not self.valid or self.key() not in self.data:
            return connection
        if self.data[self.key()]:
            self.adjuvant = True
            self.logger.warning("Adjuvant %s required" % self.name)
        else:
            self.logger.debug("Adjuvant %s skipped" % self.name)
        return connection


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
    action_type = 'deploy'

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

        candidates = cls.__subclasses__()  # pylint: disable=no-member
        willing = [c for c in candidates if c.accepts(device, parameters)]

        if len(willing) == 0:
            raise NotImplementedError(
                "No deployment strategy available for the given "
                "device '%s'. %s" % (device['hostname'], cls))

        # higher priority first
        prioritized = sorted(willing, lambda x, y: cmp(y.priority, x.priority))

        return prioritized[0]


class Boot(object):
    """
    Allows selection of the boot method for this job within the parser.
    """

    priority = 0
    action_type = 'boot'

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
        candidates = cls.__subclasses__()  # pylint: disable=no-member
        willing = [c for c in candidates if c.accepts(device, parameters)]
        if len(willing) == 0:
            raise NotImplementedError(
                "No boot strategy available for the device "
                "'%s' with the specified job parameters. %s" % (device['hostname'], cls)
            )

        # higher priority first
        prioritized = sorted(willing, lambda x, y: cmp(y.priority, x.priority))

        return prioritized[0]


class LavaTest(object):  # pylint: disable=abstract-class-not-used
    """
    Allows selection of the LAVA test method for this job within the parser.
    """

    priority = 1
    action_type = 'test'

    def __init__(self, parent):
        self.__parameters__ = {}
        self.pipeline = parent
        self.job = parent.job

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
        candidates = cls.__subclasses__()  # pylint: disable=no-member
        willing = [c for c in candidates if c.accepts(device, parameters)]
        if len(willing) == 0:
            if hasattr(device, 'parameters'):
                msg = "No test strategy available for the device "\
                      "'%s' with the specified job parameters. %s" % (device['hostname'], cls)
            else:
                msg = "No test strategy available for the device. %s" % cls
            raise NotImplementedError(msg)

        # higher priority first
        prioritized = sorted(willing, lambda x, y: cmp(y.priority, x.priority))

        return prioritized[0]


class PipelineContext(object):  # pylint: disable=too-few-public-methods
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

    If a particular piece of data is used in multiple places, use the 'common'
    area to avoid all classes needing to know which class populated the data.
    """

    # FIXME: needs to pick up minimal general purpose config, e.g. proxy or cookies
    def __init__(self):
        self.pipeline_data = {'common': {}}
