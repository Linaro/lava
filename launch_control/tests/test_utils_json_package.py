"""
Test cases for launch_control.json_utils module
"""

from unittest import TestCase

from launch_control.utils.json import (
        ClassRegistry,
        IComplexJSONType,
        IFundamentalJSONType,
        ISimpleJSONType,
        PlainOldData,
        PluggableJSONDecoder,
        PluggableJSONEncoder,
        json,
        )


class ClassRegistryTestCase(TestCase):

    def setUp(self):
        self.registry = ClassRegistry()

    def test_register(self):
        class C(IComplexJSONType):
            @classmethod
            def get_json_class_name(self):
                return "class_c"
        self.registry.register(C)
        self.assertTrue('class_c' in self.registry.registered_types)
        self.assertEqual(self.registry.registered_types['class_c'], C)

    def test_register_checks_base_class(self):
        class C(object):
            pass
        self.assertRaises(TypeError, self.registry.register, C)


class IFundamentalJSONTypeTestCase(TestCase):

    def test_unimplemented_methods(self):
        class C(IFundamentalJSONType):
            pass
        self.assertRaises(NotImplementedError, C().to_raw_json)
        self.assertRaises(NotImplementedError, C.from_json, None)

    def test_register_rejects_fundamental_types(self):
        self.assertRaises(TypeError, ClassRegistry.register, IFundamentalJSONType)

    def test_encoding(self):
        class C(IFundamentalJSONType):
            def __init__(self, raw_data):
                self.raw_data = raw_data
            def to_raw_json(self):
                return self.raw_data
        self.assertEqual(json.dumps(C("foo"), cls=PluggableJSONEncoder), "foo")
        self.assertEqual(json.dumps(C("15"), cls=PluggableJSONEncoder), "15")
        self.assertEqual(json.dumps(C("{"), cls=PluggableJSONEncoder), "{")
        self.assertEqual(json.dumps(C("#"), cls=PluggableJSONEncoder), "#")


class ISimpleJSONTypeTestCase(TestCase):

    def test_unimplemented_methods(self):
        class C(ISimpleJSONType):
            pass
        self.assertRaises(NotImplementedError, C().to_json)
        self.assertRaises(NotImplementedError, C.from_json, None)

    def test_register_rejects_simple_types(self):
        self.assertRaises(TypeError, ClassRegistry.register, ISimpleJSONType)

    def test_encoding_and_decoding(self):
        class Enum(ISimpleJSONType):
            VALUES = [] # need to subclass
            def __init__(self, value):
                self.value = value
            def to_json(self):
                return self.VALUES[self.value]
            @classmethod
            def from_json(cls, json_string):
                return cls(cls.VALUES.index(json_string))
        class Weekday(Enum):
            VALUES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday"]
        for i in range(len(Weekday.VALUES)):
            day = Weekday(i)
            json_text = json.dumps(day, cls=PluggableJSONEncoder)
            self.assertEqual(json_text, '"' + Weekday.VALUES[i] + '"')
            day_loaded = json.loads(json_text, cls=PluggableJSONDecoder,
                    type_expr=Weekday)
            self.assertEqual(day_loaded.value, day.value)


class IComplexJSONTypeTestCase(TestCase):

    def setUp(self):
        class C(IComplexJSONType):
            pass
        self.C = C

    def test_unimplemented_methods(self):
        self.assertRaises(NotImplementedError, self.C.get_json_class_name)
        self.assertRaises(NotImplementedError, self.C().to_json)
        self.assertRaises(NotImplementedError, self.C().from_json, '')
        self.assertRaises(NotImplementedError, self.C.get_json_attr_types)


class PluggableJSONEncoderTestCase(TestCase):

    def test_encoder_checks_base_class(self):
        class C(object):
            pass
        self.assertRaises(TypeError, json.dumps, C(),
                cls=PluggableJSONEncoder)


class PluggableJSONDecoderTetsCase(TestCase):

    def setUp(self):
        self.registry = ClassRegistry()

    def test_decoder_raises_TypeError_with_unregistered_class(self):
        self.assertRaises(TypeError, json.loads, '{"__class__": "C"}',
                cls=PluggableJSONDecoder, registry=self.registry)


class EncodingTestCase(TestCase):

    def setUp(self):
        class A(PlainOldData):
            def __init__(self, yy, xx):
                self.yy = yy
                self.xx = xx
        class B(PlainOldData):
            def __init__(self, qq):
                self.qq = qq
        self.obj = A(xx=A(xx="inner", yy="member"), yy=B("quax"))

    def test_nested(self):
        json_text = json.dumps(self.obj, cls=PluggableJSONEncoder,
                sort_keys=True)
        expected_json_text = '{"__class__": "A", "xx": {' \
                '"__class__": "A", "xx": "inner", "yy": "member"}, ' \
                '"yy": {"__class__": "B", "qq": "quax"}}'
        self.assertEqual(json_text, expected_json_text)

    def test_nested_custom_hints(self):
        json_text = json.dumps(self.obj, cls=PluggableJSONEncoder,
                sort_keys=True, class_hint='klass')
        expected_json_text = '{"klass": "A", "xx": {' \
                '"klass": "A", "xx": "inner", "yy": "member"}, ' \
                '"yy": {"klass": "B", "qq": "quax"}}'
        self.assertEqual(json_text, expected_json_text)

    def test_registry_is_used_to_find_proxy(self):
        class X(object):
            def __init__(self, a):
                self.a = a
        class XProxy(IComplexJSONType):
            def __init__(self, obj):
                self.obj = obj
            def to_json(self):
                return {'value': self.obj.a}
            @classmethod
            def get_json_class_name(cls):
                return 'X'
        registry = ClassRegistry()
        registry.register_proxy(X, XProxy)
        x = X('foo')
        self.assertRaises(TypeError, json.dumps,
                x, cls=PluggableJSONEncoder,
                registry=ClassRegistry())
        json_text = json.dumps(x, cls=PluggableJSONEncoder,
                registry=registry, sort_keys=True)
        expected_json_text = '{"__class__": "X", "value": "foo"}'
        self.assertEqual(json_text, expected_json_text)


class FundamentalTypeProxying(TestCase):

    def setUp(self):
        class X(object):
            def __init__(self, a):
                self.a = a
        class XProxy(IFundamentalJSONType):
            def __init__(self, obj):
                self.obj = obj
            def to_raw_json(self):
                return self.obj.a
        self.registry = ClassRegistry()
        self.registry.register_proxy(X, XProxy)
        self.x = X('5')

    def test_encoding_with_hints(self):
        json_text = json.dumps(self.x,
                cls=PluggableJSONEncoder,
                registry=self.registry)
        self.assertEqual(json_text, '5')

    def test_encoding_without_hints(self):
        json_text = json.dumps(self.x,
                cls=PluggableJSONEncoder,
                registry=self.registry,
                class_hint=None)
        self.assertEqual(json_text, '5')

class SimpleTypeProxying(TestCase):
    
    def setUp(self):
        class Integer(object):
            def __init__(self, value):
                self.value = value
        class IntegerProxy(ISimpleJSONType):
            """
            Proxy class encoding Integers as strings
            """
            def __init__(self, obj):
                self.obj = obj
            def to_json(self):
                return str(self.obj.value)
            @classmethod
            def from_json(cls, json_str):
                return Integer(int(json_str))
        class Foo(IComplexJSONType):
            def __init__(self, i):
                self.i = i
            def to_json(self):
                return {'int': self.i}
            @classmethod
            def from_json(self, json_doc):
                return Foo(json_doc['int'])
            @classmethod
            def get_json_class_name(cls):
                return 'Foo'
            @classmethod
            def get_json_attr_types(cls):
                return {'int': self.Integer}
        self.Integer = Integer
        self.Foo = Foo
        self.registry = ClassRegistry()
        self.registry.register(Foo)
        self.registry.register_proxy(Integer, IntegerProxy)

    def test_encoding_with_hints(self):
        json_text = json.dumps(
                self.Integer(5),
                cls=PluggableJSONEncoder,
                registry=self.registry)
        self.assertEqual(json_text, '"5"')

    def test_encoding_without_hints(self):
        json_text = json.dumps(
                self.Integer(6),
                cls=PluggableJSONEncoder,
                registry=self.registry,
                class_hint=None)
        self.assertEqual(json_text, '"6"')

    def test_decoding_with_type_expr(self):
        obj = json.loads(
                '"5"',
                cls=PluggableJSONDecoder,
                registry=self.registry,
                type_expr=self.Integer)
        self.assertTrue(isinstance(obj, self.Integer))
        self.assertEqual(obj.value, 5)

    def test_decoding_without_type_expr(self):
        obj = json.loads(
                '"5"',
                cls=PluggableJSONDecoder,
                registry=self.registry)
        # Nope, it's not going to work
        self.assertEqual(obj, "5")

    def test_decoding_without_type_expr_in_nested_object_with_hinting(self):
        obj = json.loads(
                '{"__class__": "Foo", "int": "5"}',
                cls=PluggableJSONDecoder,
                registry=self.registry)
        self.assertTrue(isinstance(obj, self.Foo))
        self.assertTrue(isinstance(obj.i, self.Integer))
        self.assertEqual(obj.i.value, 5)

    def test_decoding_with_type_expr_in_nested_object_without_hinting(self):
        obj = json.loads('{"int": "5"}',
                cls=PluggableJSONDecoder,
                registry=self.registry,
                type_expr=self.Foo)
        self.assertTrue(isinstance(obj, self.Foo))
        self.assertTrue(isinstance(obj.i, self.Integer))
        self.assertEqual(obj.i.value, 5)





