from __future__ import absolute_import

from .. import DefaultClassRegistry, IFundamentalJSONType

from decimal import Decimal


class DecimalProxy(IFundamentalJSONType):

    def __init__(self, obj):
        self._obj = obj

    def to_raw_json(self):
        yield str(self._obj)

    @classmethod
    def from_json(cls, json_doc):
        return Decimal(json_doc)


DefaultClassRegistry.register_proxy(Decimal, DecimalProxy)
