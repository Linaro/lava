"""
Module with non-database helper classes
"""
import datetime
import decimal
import uuid

from launch_control.models import DashboardBundle
from launch_control.utils.json import (
    ClassRegistry,
    PluggableJSONDecoder,
    json,
)
from launch_control.utils.json.proxies.datetime import datetime_proxy
from launch_control.utils.json.proxies.decimal import DecimalProxy
from launch_control.utils.json.proxies.timedelta import timedelta_proxy
from launch_control.utils.json.proxies.uuid import UUIDProxy


class DocumentError(ValueError):
    """
    Document error is raised when JSON document is malformed in any way
    """
    def __init__(self, msg):
        super(DocumentError, self).__init__(msg)


class BundleDeserializer(object):
    """
    Helper class for de-serializing JSON bundle content into database models
    """
    def __init__(self):
        self.registry = ClassRegistry()
        self._register_proxies()

    def _register_proxies(self):
        self.registry.register_proxy(datetime.datetime, datetime_proxy)
        self.registry.register_proxy(datetime.timedelta, timedelta_proxy)
        self.registry.register_proxy(uuid.UUID, UUIDProxy)
        self.registry.register_proxy(decimal.Decimal, DecimalProxy)

    def json_to_memory_model(self, json_text):
        """
        Load a memory model (based on launch_control.models) from
        specified JSON text. Raises DocumentError on any exception.
        """
        try:
            return json.loads(
                json_text, cls=PluggableJSONDecoder,
                registry=self.registry, type_expr=DashboardBundle,
                parse_float=decimal.Decimal)
        except Exception as ex:
            raise DocumentError(
                "Unable to load document: {0}".format(ex))

    def memory_model_to_db_model(self, c_bundle):
        """
        Translate a memory model to database model
        """
        raise NotImplementedError(self.memory_model_to_db_model)
