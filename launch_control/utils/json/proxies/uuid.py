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
Module with proxy type for uuid.UUID
"""

from __future__ import absolute_import
from uuid import UUID

from ..interface import ISimpleJSONType
from ..registry import DefaultClassRegistry


class UUIDProxy(ISimpleJSONType):

    def __init__(self, obj):
        self._obj = obj

    def to_json(self):
        return str(self._obj)

    @classmethod
    def from_json(self, doc):
        return UUID(doc)


DefaultClassRegistry.register_proxy(UUID, UUIDProxy)
