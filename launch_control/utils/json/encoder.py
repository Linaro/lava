"""
Module with PluggableJSONEncoder
"""

from __future__ import absolute_import

from .impl import json
from .interface import (
        IComplexJSONType,
        IFundamentalJSONType,
        ISimpleJSONType,
        )
from .registry import DefaultClassRegistry


class PluggableJSONEncoder(json.JSONEncoder):
    """
    A simple JSONEncoder that supports pluggable serializers.

    Anything that implements IFundamentalJSONType, ISimpleJSONType and
    IComplexJSONType (including the PlainOldData class) can be
    automatically encoded.
    """

    def __init__(self, registry=None, class_hint=u'__class__', **kwargs):
        """
        Initialize PluggableJSONDecoder with specified registry.

        If not specified DefaultClassRegistry is used by default.
        The registry will be used to look up proxies for objects
        that do not support native JSON encoding.

        The encoder can insert class hints into the generated JSON
        document. If class_hint is set to None the hints will be
        entirely disabled and static type hints will be required to
        decode the document back to its original form. Otherwise an
        extra field will be appended to all IComplexJSONType instances
        that will simplify decoding. The name of the field is taken from
        the class_hint argument.

        Note that ISimpleJSONType and IFundamentalJSONType cannot use
        this feature and always require static type hinting to decode.

        All other arguments are passed to JSONDecoder.__init__()
        """
        self._registry = registry or DefaultClassRegistry
        self._class_hint = class_hint
        super(PluggableJSONEncoder, self).__init__(**kwargs)

    def iterencode(self, obj, **kwargs):
        """
        Overridden method of JSONEncoder that serializes all
        IFundamentalJSONType instances.

        Hacking this method is really required to allow other numeric
        types. Since JSONEncoder only understands floats and integers
        if you want to print _precise_ value of your object (such as Decimal)
        you either have to convert it to a string (which works but is not
        correct, technically) or convert it to a float and loose precision.

        This method allows us to do the right thing by allowing
        IFundamentalJSONType instances to emit any strings they like.
        """
        obj = self._registry.get_proxy_for_object(obj)
        if isinstance(obj, IFundamentalJSONType):
            return obj.to_raw_json()
        else:
            return super(PluggableJSONEncoder, self).iterencode(obj, **kwargs)

    def default(self, obj):
        """
        Overridden method of JSONEncoder that serializes all
        ISimpleJSONType and IComplexJSONType instances.
        """
        obj = self._registry.get_proxy_for_object(obj)
        if isinstance(obj, IComplexJSONType):
            json_doc = obj.to_json()
            if self._class_hint is not None:
                json_doc[self._class_hint] = obj.get_json_class_name()
            return json_doc
        elif isinstance(obj, ISimpleJSONType):
            return obj.to_json()
        else:
            return super(PluggableJSONEncoder, self).default(obj)
