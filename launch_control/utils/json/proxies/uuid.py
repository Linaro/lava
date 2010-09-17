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
    def from_json(self, json_str):
        if not isinstance(json_str, basestring):
            raise TypeError("Unable to decode UUID from a non-string")
        return UUID(json_str)


DefaultClassRegistry.register_proxy(UUID, UUIDProxy)
