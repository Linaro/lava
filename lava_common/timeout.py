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


class Timeout:
    """
    The Timeout class is a declarative base which any actions can use. If an Action has
    a timeout, that timeout name and the duration will be output as part of the action
    description and the timeout is then exposed as a modifiable value via the device_type,
    device or even job inputs. All timeouts are subject to a hardcoded maximum duration which
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
        duration = datetime.timedelta(
            days=data.get("days", 0),
            hours=data.get("hours", 0),
            minutes=data.get("minutes", 0),
            seconds=data.get("seconds", 0),
        )
        if not duration:
            return Timeout.default_duration()
        return int(duration.total_seconds())

    def can_skip(self, parameters):
        return parameters.get("timeout", {}).get("skip", False)

    def _timed_out(self, signum, frame):
        duration = int(time.monotonic() - self.start)
        raise self.exception("%s timed out after %s seconds" % (self.name, duration))

    @contextmanager
    def __call__(self, parent, action_max_end_time):
        self.start = time.monotonic()

        max_end_time = self.start + self.duration
        if action_max_end_time is not None:
            # action_max_end_time is None when called by the job class directly
            max_end_time = min(action_max_end_time, max_end_time)

        duration = round(max_end_time - self.start)
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

            # Restore the parent handler and timeout
            # This will be None when called by Job class
            if parent is None:
                signal.alarm(0)
            else:
                signal.signal(signal.SIGALRM, parent.timeout._timed_out)
                duration = round(action_max_end_time - time.monotonic())
                if duration <= 0:
                    signal.alarm(0)
                    parent.timeout._timed_out(None, None)
                signal.alarm(duration)
        except Exception:
            # clear the timeout alarm, the action has returned an error
            signal.alarm(0)
            raise
        finally:
            self.elapsed_time = time.monotonic() - self.start
