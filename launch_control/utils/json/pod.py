from __future__ import absolute_import

from .interface import IComplexJSONType


class PlainOldData(IComplexJSONType):
    """
    Helper class for creating POD-like classes.

    Most "easy" classes can be serialized by simply inheriting
    from PlainOldData. If you want to create prettier documents
    you must implement one method with static type hinting.

    This class is designed for a NamedTuple kind of classes where you
    simply dump all public properties/attributes. It has some extra
    logic for using getters when you have private attributes. To work
    correctly it also requires a convention where all public properties
    (that are serialized) can be passed to the constructor as named
    arguments to recreate identical objects.

    As a final bonus inheriting from this class gives you a __cmp__()
    method for comparison, a __repr__() method for pretty printing.
    Both methods are backed by a special property pod_attrs that returns
    sorted list of POD attribute names.

    Note that PlainOldData supports both __slots__ and __dict__ classes.
    """

    @property
    def pod_attrs(self):
        """
        Return a list of sorted attributes.

        This works with all public attributes:
        >>> class Person(PlainOldData):
        ...     def __init__(self, name):
        ...         self.name = name
        >>> joe = Person('Joe')
        >>> joe.pod_attrs
        ('name',)

        With private attributes exposed as properties:
        >>> class Person(PlainOldData):
        ...     def __init__(self, name):
        ...         self._name = name
        ...     @property
        ...     def name(self):
        ...         return self._name
        >>> joe = Person('Joe')
        >>> joe.pod_attrs
        ('name',)

        And with __slots__:
        >>> class Person(PlainOldData):
        ...     __slots__ = ('_name',)
        ...     def __init__(self, name):
        ...         self._name = name
        ...     @property
        ...     def name(self):
        ...         return self._name
        >>> joe = Person('Joe')
        >>> joe.pod_attrs
        ('name',)

        """
        if hasattr(self, '__pod_attrs__') and self.__pod_attrs__ is not None:
            return self.__pod_attrs__
        public_attrs = []
        if hasattr(self, '__slots__'):
            to_process = self.__slots__
        else:
            to_process = self.__dict__.iterkeys()
        for attr_name in to_process:
            if attr_name.startswith('_'):
                attr_value = getattr(self.__class__, attr_name[1:], None)
                if isinstance(attr_value, property):
                    public_attrs.append(attr_name[1:])
            else:
                public_attrs.append(attr_name)
        public_attrs = tuple(sorted(public_attrs))
        if hasattr(self, '__pod_attrs__'):
            self.__pod_attrs__ = public_attrs
        return public_attrs

    @classmethod
    def get_json_class_name(cls):
        return cls.__name__

    def to_json(self):
        """
        Convert an instance to a JSON-compatible document.

        This function simply puts all public attributes that are not
        None inside the JSON document.
        """
        doc = {}
        for attr in self.pod_attrs:
            value = getattr(self, attr)
            if value is not None and value != {} and value != []:
                doc[attr] = value
        return doc

    @classmethod
    def from_json(cls, json_doc):
        """
        Create an object based on the specified JSON document. Assumes
        all fields can be passed to the constructor as named arguments.
        """
        # Re-encode all keywords to ASCII, this prevents python
        # 2.6.4 from raising an exception:
        # TypeError: __init__() keywords must be strings 
        json_doc = dict([(kw.encode('ASCII'), value) \
                for (kw, value) in json_doc.iteritems()])
        return cls(**json_doc)

    def __cmp__(self, other):
        """
        Compare two POD objects of the same class.

        Objects are compared field-by-field, sorted by attribute name
        (as returned by pod_attrs). The result is the comparison of
        first non-equal field or 0 if all fields compare equal.
        """
        if type(self) != type(other):
            return cmp(id(self), id(other))
        for attr in self.pod_attrs:
            result = cmp(getattr(self, attr), getattr(other, attr))
            if result != 0:
                break
        return result

    def __repr__(self):
        """
        Produce more-less human readable encoding of all fields.

        This function simply shows all fields in a simple format:
        >>> class Person(PlainOldData):
        ...     def __init__(self, name):
        ...         self._name = name
        ...     @property
        ...     def name(self):
        ...         return self._name
        >>> Person("Bob")
        <Person name:'Bob'>

        Note that implementation details such as slots and properties
        are hidden.  The produced string uses the public API to access
        all data. In this example the real name is stored in
        '_name' attribute of an instance __dict__ dictionary.
        """
        fields = ["%s:%r" % (attr, getattr(self, attr)) \
                for attr in self.pod_attrs]
        return "<%s %s>" % (self.__class__.__name__, " ".join(fields))
