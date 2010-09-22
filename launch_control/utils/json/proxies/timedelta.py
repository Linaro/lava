# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Module with proxy type for datetime.timedelta
"""
from __future__ import absolute_import
from datetime import timedelta
import re

from ..interface import ISimpleJSONType
from ..registry import DefaultClassRegistry


class timedelta_proxy(ISimpleJSONType):
    """
    Proxy for serializing datetime.timedelta instances
    """

    def __init__(self, obj):
        self._obj = obj

    def to_json(self):
        """
        Serialize wrapped datetime.timedelta instance to a string the
        with the following format:
            [DAYS]d [SECONDS]s [MICROSECONDS]us
        """
        return "{0}d {1}s {2}us".format(
                self._obj.days, self._obj.seconds, self._obj.microseconds)

    @classmethod
    def from_json(self, json_doc):
        """
        Deserialize JSON document (string) to datetime.timedelta instance
        """
        if not isinstance(json_doc, basestring):
            raise TypeError("JSON document must be a string")
        match = re.match("^(\d+)d (\d+)s (\d+)us$", json_doc)
        if not match:
            raise ValueError("JSON document must match expected pattern")
        days, seconds, microseconds = map(int, match.groups())
        return timedelta(days, seconds, microseconds)


DefaultClassRegistry.register_proxy(timedelta, timedelta_proxy)

