# Copyright (C) 2010 Linaro Limited
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
Module with proxy type for decimal.Decimal
"""

from __future__ import absolute_import
from decimal import Decimal

from ..interface import IFundamentalJSONType
from ..registry import DefaultClassRegistry

class DecimalProxy(IFundamentalJSONType):
    """
    Proxy type implementing IFundamentalJSONType for decimal.Decimal
    """

    def __init__(self, obj):
        self._obj = obj

    def to_raw_json(self):
        yield str(self._obj)

    @classmethod
    def from_json(cls, json_doc):
        return Decimal(json_doc)


DefaultClassRegistry.register_proxy(Decimal, DecimalProxy)
