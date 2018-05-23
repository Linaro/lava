# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.


import datetime
import time
import signal
from contextlib import contextmanager
from lava_common.constants import ACTION_TIMEOUT
from lava_common.exceptions import JobError, ConfigurationError


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
    def __init__(self, name, duration=ACTION_TIMEOUT, exception=JobError):
        self.name = name
        self.start = 0
        self.elapsed_time = -1
        self.duration = duration  # Actions can set timeouts higher than the clamp.
        self.exception = exception

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
        raise self.exception("%s timed out after %s seconds" % (self.name, duration))

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
            # Deactivate any previous alarm and set elapse_time prior to raise
            signal.alarm(0)
            self.elapsed_time = 0
            self._timed_out(None, None)

        signal.signal(signal.SIGALRM, self._timed_out)
        signal.alarm(duration)

        try:
            yield max_end_time
        finally:
            # clear the timeout alarm, the action has returned
            signal.alarm(0)
            self.elapsed_time = time.time() - self.start
