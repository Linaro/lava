# Copyright (c) 2010 Linaro Limited
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
Test cases for launch_control.json_utils module
"""

from unittest import TestCase

from launch_control.utils.json import (
        ClassRegistry,
        DefaultClassRegistry,
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

    def test_default_registry_exists(self):
        self.assertTrue(isinstance(DefaultClassRegistry, ClassRegistry))

    def test_register_works_for_complex_types(self):
        class C(IComplexJSONType):
            @classmethod
            def get_json_class_name(self):
                return "class_c"
        self.registry.register(C)
        self.assertTrue('class_c' in self.registry.registered_types)
        self.assertEqual(self.registry.registered_types['class_c'], C)

    def test_register_rejects_fundamental_types(self):
        self.assertRaises(TypeError,
                self.registry.register, IFundamentalJSONType)

    def test_register_rejects_simple_types(self):
        self.assertRaises(TypeError,
                self.registry.register, ISimpleJSONType)

    def test_register_rejects_other_types(self):
        class C(object): pass
        self.assertRaises(TypeError, self.registry.register, C)

    def test_register_proxy_works_for_fundamental_types(self):
        class C(object): pass
        class CProxy(IFundamentalJSONType): pass
        self.registry.register_proxy(C, CProxy)
        # forward mapping
        self.assertTrue(C in self.registry.proxies)
        self.assertEqual(self.registry.proxies[C], CProxy)
        # backward mapping
        self.assertTrue(CProxy in self.registry.proxied)
        self.assertEqual(self.registry.proxied[CProxy], C)

    def test_register_proxy_works_for_simple_types(self):
        class C(object): pass
        class CProxy(ISimpleJSONType): pass
        self.registry.register_proxy(C, CProxy)
        # forward mapping
        self.assertTrue(C in self.registry.proxies)
        self.assertEqual(self.registry.proxies[C], CProxy)
        # backward mapping
        self.assertTrue(CProxy in self.registry.proxied)
        self.assertEqual(self.registry.proxied[CProxy], C)

    def test_register_proxy_works_for_complex_types(self):
        class C(object): pass
        class CProxy(IComplexJSONType):
            @classmethod
            def get_json_class_name(self):
                return "C"
        self.registry.register_proxy(C, CProxy)
        # forward mapping
        self.assertTrue(C in self.registry.proxies)
        self.assertEqual(self.registry.proxies[C], CProxy)
        # backward mapping
        self.assertTrue(CProxy in self.registry.proxied)
        self.assertEqual(self.registry.proxied[CProxy], C)
        # complex type proxy is also registered by name
        self.assertTrue("C" in self.registry.registered_types)
        self.assertEqual(self.registry.registered_types["C"], CProxy)

    def test_get_proxy_for_object_ignores_unproxied_classes(self):
        obj = object()
        proxy_obj = self.registry.get_proxy_for_object(obj)
        self.assertEqual(obj, proxy_obj)

    def test_get_proxy_for_object_maps_proxied_types(self):
        class C(object): pass
        class CProxy(IFundamentalJSONType): # actual base class is not important
            def __init__(self, c):
                self.c = c
        self.registry.register_proxy(C, CProxy)
        c = C()
        c_proxy = self.registry.get_proxy_for_object(c)
        self.assertTrue(isinstance(c_proxy, CProxy))
        self.assertEqual(c_proxy.c, c)

    def test_register_proxy_checks_bad_calls(self):
        class C(object): pass
        class CProxy(IFundamentalJSONType): pass
        # swapped arguments
        self.assertRaises(TypeError,
                self.registry.register_proxy, CProxy, C)
        # proxied type not needing proxy
        self.assertRaises(TypeError,
                self.registry.register_proxy, CProxy, CProxy)


class FundamentalTypeBasics(TestCase):

    class DirectOutput(IFundamentalJSONType):
        def __init__(self, raw_data):
            self.raw_data = raw_data
        def to_raw_json(self):
            return self.raw_data

    def setUp(self):
        self.registry = ClassRegistry()

    def test_unimplemented_methods(self):
        self.assertRaises(NotImplementedError,
                IFundamentalJSONType().to_raw_json)
        self.assertRaises(NotImplementedError,
                IFundamentalJSONType.from_json, None)

    def test_encoding_output(self):
        for text in ["foo", "15", "{", "#"]:
            obj = self.DirectOutput(text)
            json_text = json.dumps(obj,
                    cls=PluggableJSONEncoder,
                    registry=self.registry)
            self.assertEqual(json_text, text)

    def test_encoding_hints_not_relevant1(self):
        json_text = json.dumps(
                self.DirectOutput('5'),
                cls=PluggableJSONEncoder,
                registry=self.registry,
                class_hint="this value will be ignored")
        self.assertEqual(json_text, '5')

    def test_encoding_hints_not_relevant2(self):
        json_text = json.dumps(
                self.DirectOutput('5'),
                cls=PluggableJSONEncoder,
                registry=self.registry,
                class_hint=None)
        self.assertEqual(json_text, '5')


class FundamentalTypeProxying(FundamentalTypeBasics):
    # This inherits all tests from FundamentalTypeBasics
    # The tests are identical, the only difference is that
    # DirectOutput is no longer a json type and a proxy is used instead.

    class DirectOutput(object):
        def __init__(self, raw_data):
            self.raw_data = raw_data

    class DirectOutputProxy(IFundamentalJSONType):
        def __init__(self, obj):
            self.obj = obj
        def to_raw_json(self):
            return self.obj.raw_data

    def setUp(self):
        super(FundamentalTypeProxying, self).setUp()
        self.registry.register_proxy(self.DirectOutput, self.DirectOutputProxy)


class SimpleTypeTestsMixIn(object):

    def test_encoding_output(self):
        for i in range(len(self.Weekday.VALUES)):
            day = self.Weekday(i)
            json_text = json.dumps(day,
                    cls=PluggableJSONEncoder,
                    registry=self.registry)
            expected_json_text = '"{0}"'.format(self.Weekday.VALUES[i])
            self.assertEqual(json_text, expected_json_text)

    def test_encoding_with_helper(self):
        for i in range(len(self.Weekday.VALUES)):
            day = self.Weekday(i)
            helper = self.Helper(day)
            json_text = json.dumps(helper,
                    cls=PluggableJSONEncoder,
                    registry=self.registry,
                    sort_keys=True)
            # format is not json friendly with all the { } and you need
            # to escape.
            expected_json_text = ('{{"__class__": "Helper", '
                    '"inner": "{0}"}}'.format(self.Weekday.VALUES[i]))
            self.assertEqual(json_text, expected_json_text)

    def test_encoding_with_helper_and_no_hints(self):
        for i in range(len(self.Weekday.VALUES)):
            day = self.Weekday(i)
            helper = self.Helper(day)
            json_text = json.dumps(helper,
                    cls=PluggableJSONEncoder,
                    registry=self.registry,
                    class_hint=None,
                    sort_keys=True)
            # format is not json friendly with all the { } and you need
            # to escape.
            expected_json_text = '{{"inner": "{0}"}}'.format(
                    self.Weekday.VALUES[i])
            self.assertEqual(json_text, expected_json_text)

    def test_decoding_with_type_expr(self):
        for i in range(len(self.Weekday.VALUES)):
            json_text = '"' + self.Weekday.VALUES[i] + '"'
            day_loaded = json.loads(json_text,
                    cls=PluggableJSONDecoder,
                    registry=self.registry,
                    type_expr=self.Weekday)
            self.assertTrue(isinstance(day_loaded, self.Weekday))
            self.assertEqual(day_loaded.value, i)


class SimpleTypeBasics(TestCase, SimpleTypeTestsMixIn):

    def setUp(self):
        class Weekday(ISimpleJSONType):
            VALUES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday"]
            def __init__(self, value):
                self.value = value
            def to_json(self):
                return self.VALUES[self.value]
            @classmethod
            def from_json(cls, json_string):
                return cls(cls.VALUES.index(json_string))

        class Helper(IComplexJSONType):
            """ Helper class that wraps our Weekday class """
            def __init__(self, inner):
                self.inner = inner
            def to_json(self):
                return {'inner': self.inner}
            @classmethod
            def from_json(cls, json_doc):
                return cls(json_doc['inner'])
            @classmethod
            def get_json_class_name(cls):
                return 'Helper'
            @classmethod
            def get_json_attr_types(cls):
                return {'inner': Weekday}
        self.Weekday = Weekday
        self.Helper = Helper
        self.registry = ClassRegistry()
        self.registry.register(Helper)

    def test_unimplemented_methods(self):
        class C(ISimpleJSONType):
            pass
        self.assertRaises(NotImplementedError, C().to_json)
        self.assertRaises(NotImplementedError, C.from_json, None)


class SimpleTypeProxying(TestCase, SimpleTypeTestsMixIn):

    def setUp(self):
        class Weekday(object):
            VALUES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday"]
            def __init__(self, value):
                self.value = value

        class WeekdayProxy(ISimpleJSONType):
            def __init__(self, obj):
                self.obj = obj
            def to_json(self):
                return self.obj.VALUES[self.obj.value]
            @classmethod
            def from_json(cls, json_string):
                return Weekday(Weekday.VALUES.index(json_string))

        class Helper(IComplexJSONType):
            def __init__(self, inner):
                self.inner = inner
            def to_json(self):
                return {'inner': self.inner}
            @classmethod
            def from_json(cls, json_doc):
                return cls(json_doc['inner'])
            @classmethod
            def get_json_class_name(cls):
                return 'Helper'
            @classmethod
            def get_json_attr_types(cls):
                return {'inner': Weekday}

        self.Weekday = Weekday
        self.Helper = Helper
        self.registry = ClassRegistry()
        self.registry.register(Helper)
        self.registry.register_proxy(Weekday, WeekdayProxy)


class ComplexTypeTestsMixIn(object):

    def test_encoding(self):
        json_text = json.dumps(
                self.Integer(5),
                cls=PluggableJSONEncoder,
                registry=self.registry,
                sort_keys=True)
        expected_json_text = '{"__class__": "Integer", "value": 5}'
        self.assertEqual(json_text, expected_json_text)

    def test_decoding_with_class_hints(self):
        json_text = '{"__class__": "Integer", "value": 5}'
        obj = json.loads(
                json_text,
                cls=PluggableJSONDecoder,
                registry=self.registry)
        self.assertTrue(isinstance(obj, self.Integer))
        self.assertEqual(obj.value, 5)

    def test_decoding_with_type_expression(self):
        json_text = '{"value": 5}'
        obj = json.loads(
                json_text,
                cls=PluggableJSONDecoder,
                registry=self.registry,
                type_expr=self.Integer)
        self.assertTrue(isinstance(obj, self.Integer))
        self.assertEqual(obj.value, 5)


class ComplexTypeBasics(TestCase, ComplexTypeTestsMixIn):

    def setUp(self):
        class Integer(IComplexJSONType):
            def __init__(self, value):
                self.value = value
            def to_json(self):
                return {"value": self.value}
            @classmethod
            def from_json(cls, json_doc):
                return cls(value = json_doc['value'])
            @classmethod
            def get_json_class_name(cls):
                return 'Integer'
        self.Integer = Integer
        self.registry = ClassRegistry()
        self.registry.register(Integer)

    def test_unimplemented_methods(self):
        class C(IComplexJSONType):
            pass
        self.assertRaises(NotImplementedError, C.get_json_class_name)
        self.assertRaises(NotImplementedError, C().to_json)
        self.assertRaises(NotImplementedError, C().from_json, '')
        self.assertRaises(NotImplementedError, C.get_json_attr_types)


class ComplexTypeProxying(TestCase, ComplexTypeTestsMixIn):

    def setUp(self):
        class Integer(object):
            def __init__(self, value):
                self.value = value

        class IntegerProxy(IComplexJSONType):
            def __init__(self, obj):
                self.obj = obj
            def to_json(self):
                return {"value": self.obj.value}
            @classmethod
            def from_json(cls, json_doc):
                return Integer(value = json_doc['value'])
            @classmethod
            def get_json_class_name(cls):
                return 'Integer'

        self.Integer = Integer
        self.IntegerProxy = IntegerProxy
        self.registry = ClassRegistry()
        self.registry.register_proxy(Integer, IntegerProxy)

    def test_proxy_types_require_registration(self):
        # Use empty registry
        registry = ClassRegistry()
        self.assertRaises(TypeError, json.dumps,
                self.Integer(5), cls=PluggableJSONEncoder,
                registry=registry)

    def test_proxy_decoding_with_proxy_type_expression(self):
        json_text = '{"value": 5}'
        obj = json.loads(
                json_text,
                cls=PluggableJSONDecoder,
                registry=self.registry,
                type_expr=self.IntegerProxy)
        self.assertTrue(isinstance(obj, self.Integer))
        self.assertEqual(obj.value, 5)


class PODBasics(TestCase):

    def test_pod_attrs_empty(self):
        class C(PlainOldData):
            pass
        self.assertEqual(C().pod_attrs, ())

    def test_pod_attrs_simple(self):
        class C(PlainOldData):
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
        self.assertEqual(C().pod_attrs, ())
        self.assertEqual(C(a=1, b="foo").pod_attrs, ('a', 'b'))
        self.assertEqual(C(xxx="bar").pod_attrs, ('xxx',))

    def test_pod_attrs_hidden(self):
        class C(PlainOldData):
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
        self.assertEqual(C(public=1, _private=1).pod_attrs,
                ('public',))

    def test_pod_attrs_props(self):
        class C(PlainOldData):
            @property
            def foo(self):
                """ this property will not be reported as attribute """
                return 5
        self.assertEqual(C().pod_attrs, ())

    def test_pod_attrs_slots(self):
        class C(PlainOldData):
            __slots__= ('a', 'b', 'c')
        self.assertEqual(C().pod_attrs, ('a', 'b', 'c'))

    def test_pod_attrs_slots_and_hidden(self):
        class C(PlainOldData):
            __slots__ = ('a', '_b', 'c')
        self.assertEqual(C().pod_attrs, ('a', 'c'))

    def test_pod_attrs_slots_and_props(self):
        class C(PlainOldData):
            __slots__ = ('a', '_b', 'c')
            @property
            def d(self):
                """ this property will not be reported as attribute """
                return 5
        self.assertEqual(C().pod_attrs, ('a', 'c'))

    def test_pod_attrs_are_sorted(self):
        class A1(PlainOldData):
            def __init__(self, b, a):
                self.b = b
                self.a = a
        class A2(PlainOldData):
            def __init__(self, a, b):
                self.a = a
                self.b = b
        self.assertEqual(A1(None, None).pod_attrs, ('a', 'b'))
        self.assertEqual(A2(None, None).pod_attrs, ('a', 'b'))

    def test_pod_attrs_caching_disabled_by_default(self):
        class C(PlainOldData):
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
        obj = C(a=1, b=2, x=7)
        pod_attrs = obj.pod_attrs
        self.assertFalse(hasattr(obj, '__pod__attrs__'))
        self.assertEqual(pod_attrs, ('a', 'b', 'x'))
        self.assertFalse(hasattr(obj, '__pod__attrs__'))

    def test_pod_attrs_caching(self):
        class C(PlainOldData):
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.__pod_attrs__ = None
        obj = C(a=1, b=2, x=7)
        # make sure cache is empty
        self.assertTrue(obj.__pod_attrs__ is None)
        # calculate (and cache)
        pod_attrs = obj.pod_attrs
        # check value, just in case
        self.assertEqual(pod_attrs, ('a', 'b', 'x'))
        # cached value stored
        self.assertEqual(pod_attrs, obj.__pod_attrs__)
        # check that cached value is reused
        self.assertTrue(pod_attrs is obj.pod_attrs)

    def test_pod_comparison(self):
        class C(PlainOldData):
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
        self.assertTrue(C(a=1) == C(a=1))
        self.assertTrue(C(a=1, b=2) == C(a=1, b=2))
        self.assertTrue(C(a=1) > C(a=0))
        self.assertTrue(C(a=0) < C(a=1))
        self.assertTrue(C(a=0, b=0) < C(a=0, b=1))


class PODEncoding(TestCase):

    def setUp(self):
        class A(PlainOldData):
            def __init__(self, yy, xx):
                self.yy = yy
                self.xx = xx
        class B(PlainOldData):
            def __init__(self, qq):
                self.qq = qq
        self.obj = A(xx=A(xx="inner", yy="member"), yy=B("quax"))

    def test_nested_encoding(self):
        json_text = json.dumps(self.obj, cls=PluggableJSONEncoder,
                sort_keys=True)
        expected_json_text = ('{"__class__": "A", "xx": {'
                '"__class__": "A", "xx": "inner", "yy": "member"}, '
                '"yy": {"__class__": "B", "qq": "quax"}}')
        self.assertEqual(json_text, expected_json_text)

    def test_nested_encoding_with_custom_hints(self):
        json_text = json.dumps(self.obj, cls=PluggableJSONEncoder,
                sort_keys=True, class_hint='klass')
        expected_json_text = ('{"klass": "A", "xx": {' 
                '"klass": "A", "xx": "inner", "yy": "member"}, '
                '"yy": {"klass": "B", "qq": "quax"}}')
        self.assertEqual(json_text, expected_json_text)


class MiscTests(TestCase):

    def test_encoder_checks_base_class(self):
        class C(object):
            pass
        self.assertRaises(TypeError,
                json.dumps, C(), cls=PluggableJSONEncoder)

    def test_decoder_raises_TypeError_with_unregistered_class(self):
        self.assertRaises(TypeError,
                json.loads, '{"__class__": "UregisteredClass"}',
                cls=PluggableJSONDecoder, registry=ClassRegistry())
