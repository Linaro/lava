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
