"""
Class Registry for JSON type mapping and proxy classes
"""
from __future__ import absolute_import
from .interface import IComplexJSONType


class ClassRegistry(object):
    """
    Class registry for mapping class names to python classes.

    It also supports registering proxy types for things that cannot
    implement one of the serialization interfaces directly.
    """

    def __init__(self):
        self.registered_types = {}
        self.proxies = {}

    def register(self, other_cls):
        """
        Function/class decorator for marking a class as serializable.
        Register class `other_cls' in the type registry.
        """
        if not issubclass(other_cls, IComplexJSONType):
            raise TypeError("cls must be a class implementing"
                    " IComplexJSONType interface")
        name = other_cls.get_json_class_name()
        self.registered_types[name] = other_cls
        return other_cls

    def register_proxy(self, cls, proxy_cls):
        """
        Method for creating proxy types.

        This method is most useful when you need to mark certain third
        party class as JSON aware by creating a proxy class for handling
        the serialization.

        Note: this will also register the proxy_cls when appropriate
        """
        self.proxies[cls] = proxy_cls
        if issubclass(proxy_cls, IComplexJSONType):
            self.register(proxy_cls)

    def get_proxy_for_object(self, obj):
        """
        Return proxy object for specified object.
        """
        proxy = self.proxies.get(type(obj), None)
        if proxy:
            return proxy(obj)
        else:
            return obj


# Default class registry used by default
DefaultClassRegistry = ClassRegistry()
