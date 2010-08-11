from __future__ import absolute_import

from .. import (ISimpleJSONType, DefaultClassRegistry)

from uuid import UUID


class UUIDProxy(ISimpleJSONType):

    def __init__(self, obj):
        self._obj = obj

    def to_json(self):
        return str(self._obj)

    @classmethod
    def from_json(self, doc):
        return UUID(doc)


DefaultClassRegistry.register_proxy(UUID, UUIDProxy)
