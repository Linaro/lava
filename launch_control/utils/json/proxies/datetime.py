"""
Module with datetime proxy class with JSON serialization support.

Note: importing this module registers the proxy with the DefaultClassRegistry.
"""

from __future__ import absolute_import

from .. import (ISimpleJSONType, DefaultClassRegistry)

from datetime import datetime


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
