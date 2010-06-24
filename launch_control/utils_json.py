"""
Helper module for working with JSON and custom classes. This module
defines IJSONSerializable, a simple interface that allows to serialize
instances into and back from JSON.

This module also maintains a global type registry. It works in
cooperation with PluggableJSONDecoder and PluggableJSONEncoder classes.
To register a type automatically use the @IJSONSerializable.register
class decorator.

For example, this is a simple "Person" class that can be serialized and
deserialized to any stream or string using standard API from the 'json'
module.

First let's define a serializable class. Note the decorator .register that
adds the class to an internal type registry.
>>> @IJSONSerializable.register
... class Person(IJSONSerializable):
...     def __init__(self, name):
...         self.name = name
...     def to_json(self):
...         return {'name': self.name}
...     @classmethod
...     def from_json(cls, doc):
...         return cls(doc['name'])

Let's make a person instance:
>>> joe = Person('Joe')
>>> joe.name
'Joe'

We can now serialize this object using json.dumps() or any other json
module API. The only requirement is to pass our generic pluggable
encoder class:
>>> joe_str = json.dumps(joe, cls=PluggableJSONEncoder)
>>> joe_str
'{"name": "Joe", "__class__": "Person"}'

This is pretty ugly, we'll see how to get rid of __class__ later on.

To deserialize use pluggable decoder with another standard json API
>>> joe = json.loads(joe_str, cls=PluggableJSONDecoder)
>>> joe.name
u'Joe'

What's just happened? Unicode 'joe'? That's right *all* strings you push
through the system will be deserialized as unicode objects. You have to
ensure that you're okay with this.
"""

try:
    import json
except ImportError:
    import simplejson as json

class IJSONSerializable(object):
    """
    Interface for all classes that can be serialzed to JSON using
    PluggableJSONEncoder.

    Subclasses should define to_json() and from_json() and
    register with the @register decorator.
    """

    # Mapping of type-name-to IJSONSerializable-subclass
    _registered_types = {}

    @classmethod
    def register(cls, other_cls):
        """
        Class decorator for marking a class as serializable.
        Register class `other_cls' in the type registry.
        """
        if not issubclass(other_cls, IJSONSerializable):
            raise TypeError("cls must be a class implementing"
                    " IJSONSerializable interface")
        name = other_cls._get_json_class_name()
        cls._registered_types[name] = other_cls
        return other_cls

    @classmethod
    def _get_json_class_name(cls):
        """
        Return the class name to store inside JSON documents
        """
        return cls.__name__

    def to_json(self):
        """
        Serialize to a JSON-serializable object.

        The result has to be a python dictionary with any properties
        that you want to save. The same dictionary will be passed to
        from_json()

        Note that you don't have to encode the class of the instance. It
        is being implicitly added as a special __class__ field after
        this method returns.
        """
        raise NotImplementedError(self.to_json)

    @classmethod
    def from_json(cls, doc):
        """
        Initialize new instance from JSON document. The document
        contains a python dictionary with properties that were set by
        to_json()
        """
        raise NotImplementedError(cls.from_json)

class PluggableJSONDecoder(json.JSONDecoder):
    """
    JSON decoder with special support for IJSONSerializable
    """

    def _object_hook(self, obj):
        """
        Helper method for deserializing objects from their JSON
        representation.
        """
        if isinstance(obj, dict) and "__class__" in obj:
            cls_name = obj['__class__']
            try:
                cls = IJSONSerializable._registered_types[cls_name]
            except KeyError:
                raise TypeError("type %s was not registered with"
                        " PluggableJSONDecoder" % cls_name)
            # Remove the class name so that the document we pass to
            # from_json is identical as the document we've got from
            # to_json()
            del obj['__class__']
            return cls.from_json(obj)
    def __init__(self, *args, **kwargs):
        super(PluggableJSONDecoder, self).__init__(
                *args, object_hook = self._object_hook, **kwargs)


class PluggableJSONEncoder(json.JSONEncoder):
    """
    A simple JSONEncoder that supports pluggable serializers.

    Anything that subclasses from IJSONSerializable is automatically
    supported.
    """

    def default(self, obj):
        """
        Overridden method of JSONEncoder that serializes all
        IJSonSerializable instances. This method simply calls the
        to_json() method and injects the registered type name as
        '__class__' attribute.
        """
        if isinstance(obj, IJSONSerializable):
            doc = obj.to_json()
            doc['__class__'] = obj._get_json_class_name()
            return doc
        else:
            super(PluggableJSONEncoder, self).default(obj)


def _test():
    """
    Test all docstrings.

    Usage: python sample.py [-v]
    """
    import doctest
    doctest.testmod()



if __name__ == "__main__":
    _test()
