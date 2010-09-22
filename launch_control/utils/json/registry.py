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
Class Registry for JSON type mapping and proxy classes
"""
from __future__ import absolute_import
from .interface import (
        IComplexJSONType,
        IFundamentalJSONType,
        ISimpleJSONType,
        )


class ClassRegistry(object):
    """
    Class registry for mapping class names to python classes.

    It also supports registering proxy types for things that cannot
    implement one of the serialization interfaces directly.
    """

    def __init__(self):
        self.registered_types = {} # name -> proxy or cls
        self.proxies = {} # cls -> proxy
        self.proxied = {} # proxy -> cls

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
        if not isinstance(proxy_cls, type):
            raise TypeError("proxy_cls must be a type")
        if not isinstance(cls, type):
            raise TypeError("cls must be a type")
        if not issubclass(proxy_cls, (IFundamentalJSONType,
            ISimpleJSONType, IComplexJSONType)):
            raise TypeError("proxy_cls must implement one of the JSON interfaces")
        if issubclass(cls, (IFundamentalJSONType, ISimpleJSONType,
            IComplexJSONType)):
            raise TypeError("cls (proxied class) already implements one of the JSON interfaces")
        self.proxies[cls] = proxy_cls
        self.proxied[proxy_cls] = cls
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
