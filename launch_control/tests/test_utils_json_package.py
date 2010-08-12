"""
Test cases for launch_control.json_utils module
"""

from unittest import TestCase

from launch_control.thirdparty.mocker import (
        Mocker,
        MockerTestCase,
        expect)
from launch_control.utils.import_prohibitor import (
        ImportMockingTestCase,)
from launch_control.utils.json import (
        ClassRegistry,
        IComplexJSONType,
        IFundamentalJSONType,
        ISimpleJSONType,
        json)
from launch_control.utils.json.encoder import PluggableJSONEncoder
from launch_control.utils.json.decoder import PluggableJSONDecoder


__inhibit_protect__ = True


class IJSONSupportTestCase(ImportMockingTestCase):

    def test_json_import_failure(self):
        """ Make sure we import simplejson if json is not available """
        self.prohibit_importing('json')
        self.mock_imports()
        mocker = Mocker()
        obj = mocker.replace('simplejson')
        mocker.replay()
        # Needs explicit reimport after import mocking
        import launch_control.utils.json as imported_module
        self.assertTrue(imported_module.json is obj)
        mocker.verify()
        mocker.restore()


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


