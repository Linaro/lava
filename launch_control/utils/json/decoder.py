from . import (
        DefaultClassRegistry,
        IComplexJSONType,
        IFundamentalJSONType,
        ISimpleJSONType,
        mod_json)

class PluggableJSONDecoder(mod_json.JSONDecoder):
    """
    JSON decoder with special support for ISimpleJSONType and
    IComplexJSONType.
    """

    def __init__(self, registry=None, class_hint=u'__class__',
            type_expr=None, **kwargs):
        """
        Initialize PluggableJSONDecoder with specified registry.
        If not specified DefaultClassRegistry is used by default.
        All other arguments are passed to JSONDecoder.__init__()
        """
        if registry is None:
            registry = DefaultClassRegistry
        self._registry = registry
        self._type_expr = type_expr
        self._class_hint = class_hint
        super(PluggableJSONDecoder, self).__init__(
                object_hook = self._object_hook, **kwargs)

    def _object_hook(self, obj):
        """
        Helper method for deserializing objects from their JSON
        representation.
        """
        if self._class_hint not in obj:
            return obj
        cls_name = obj[self._class_hint]
        # Remove the class name so that the document we pass to
        # from_json is identical as the document we've got from
        # to_json()
        del obj[self._class_hint]
        try:
            cls = self._registry.registered_types[cls_name]
        except KeyError:
            raise TypeError("type %s was not registered with %s"
                    % (cls_name, self._registry))
        return cls.from_json(obj)

    def raw_decode(self, s, **kw):
        obj, end = super(PluggableJSONDecoder, self).raw_decode(s, **kw)
        if self._type_expr:
            obj = self._awaken(obj, self._type_expr)
        return obj, end

    def _awaken_dict(self, json_doc, type_expr):
        """
        Awaken a dictionary.
        """
        if not isinstance(json_doc, dict):
            raise ValueError("Awakened object is not a dictionary")
        #print "Waking up a dictionary with types: %r" % (type_expr,)
        for key_name, value_type in type_expr.iteritems():
            if key_name in json_doc:
                #print "Translating element %r with type %r" % (key_name, value_type)
                value = self._awaken(json_doc[key_name], value_type)
                #print "Translated element %r to value %r" % (key_name, value)
                json_doc[key_name] = value
        return json_doc

    def _awaken_list(self, json_doc, type_expr):
        """
        Awaken a list
        """
        if not isinstance(json_doc, list):
            raise ValueError("Awakened object is not a list")
        cls = type_expr[0]
        #print "Waking up a list of %s" % (cls,)
        return [self._awaken(item, cls) for item in json_doc]

    def _awaken_object(self, json_doc, type_expr):
        #print "Waking up object based on type: %r" % (type_expr,)
        cls = type_expr
        # Find a proxy class if possible
        if cls in self._registry.proxies:
            proxy_cls = self._registry.proxies[cls]
            #print "Remapped type expression to %r" % (proxy_cls,)
        else:
            proxy_cls = cls
        # The class we're working with _must_ be one of the supported
        # interfaces. Otherwise something is wrong.
        if not issubclass(proxy_cls, (IFundamentalJSONType,
            ISimpleJSONType, IComplexJSONType)):
            raise TypeError("Incorrect type expression: %r" % (proxy_cls,))
        #print "Waking up a instance of %r using %r" % (cls, proxy_cls)
        if issubclass(proxy_cls, IComplexJSONType):
            #print "Translating attributes for object of class %r" % (proxy_cls,)
            if not isinstance(json_doc, dict):
                raise ValueError("When waking up %r via %r the JSON "
                        "document was not a dictionary" % (cls,
                            proxy_cls))
            types = proxy_cls.get_json_attr_types()
            new_json_doc = {}
            for attr_name, value in json_doc.iteritems():
                if attr_name in types:
                    #print "Translating attribute %r with type %r" % (attr_name, types[attr_name])
                    value = self._awaken(value, types[attr_name])
                    #print "Translated attribute %r to value %r" % (attr_name, value)
                new_json_doc[attr_name] = value
            json_doc = new_json_doc
        #print "Attempting to instantiate %r from %r" % (cls, json_doc)
        obj = proxy_cls.from_json(json_doc)
        if not isinstance(obj, cls):
            raise TypeError("Object instantiated using %r is not of"
                    " expected type %r" % (proxy_cls, cls))
        #print "Instantiated %r" % (obj,)
        return obj

    def _awaken(self, json_doc, type_expr):
        """
        Awaken objects from their JSON representation.
        """
        if isinstance(type_expr, list):
            return self._awaken_list(json_doc, type_expr)
        if isinstance(type_expr, dict):
            return self._awaken_dict(json_doc, type_expr)
        else:
            return self._awaken_object(json_doc, type_expr)
