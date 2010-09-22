# Copyright (c) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
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
from datetime import datetime

from ..interface import ISimpleJSONType
from ..registry import DefaultClassRegistry


class datetime_proxy(ISimpleJSONType):
    """
    Proxy class for serializing datetime.datetime objects.

    The serialization is a JSON string. Date is encoded
    using the ISO 8601 format:
        YYYY-MM-DDThh:mm:ssZ

    That is:
        * Four digit year code
        * Dash
        * Two digit month code
        * Dash
        * Two digit day code
        * Capital letter 'T' - time stamp indicator
        * Two digit hour code
        * Colon
        * Two digit minute code
        * Colon
        * Two digit seconds code
        * Capital letter 'Z' - Zulu (UTC) time zone indicator
    """

    FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, obj):
        self._obj = obj

    def to_json(self):
        return self._obj.strftime(self.FORMAT)

    @classmethod
    def from_json(self, doc):
        return datetime.strptime(doc, self.FORMAT)

DefaultClassRegistry.register_proxy(datetime, datetime_proxy)
