"""
Test cases for launch_control.utils_json module
"""

from unittest import TestCase

from launch_control.thirdparty.mocker import (
        Mocker,
        MockerTestCase,
        expect)
from launch_control.utils.import_prohibitor import ImportMockingTestCase
from launch_control.utils_json import (
        ClassRegistry,
        IJSONSerializable,
        PluggableJSONDecoder,
        PluggableJSONEncoder,
        json)

# This is here to protect this module from being reloaded after import
# mocking takes place in one of the tests below. This marker is required
# because import mocking reloads all modules that depend on a module
# being prohibited to make side effects happen (such as ImportError
# being raised and alternate code-paths being taken).
__inhibit_protect__ = True


class IJSONSupportTestCase(ImportMockingTestCase):

    def test_json_import_failure(self):
        """ Make sure we import simplejson if json is not available """
        self.prohibit_importing('json')
        self.mock_imports()
        mocker = Mocker()
        obj = mocker.replace('simplejson')
        mocker.replay()
        import launch_control.utils_json
        self.assertTrue(launch_control.utils_json.json is obj)
        mocker.verify()
        mocker.restore()


class ClassRegistryTestCase(TestCase):

    def setUp(self):
        self.registry = ClassRegistry()

    def test_register(self):
        class C(IJSONSerializable):
            @classmethod
            def _get_json_class_name(self):
                return "class_c"
        self.registry.register(C)
        self.assertTrue('class_c' in self.registry.registered_types)
        self.assertEqual(self.registry.registered_types['class_c'], C)

    def test_register_checks_base_class(self):
        class C(object):
            pass
        self.assertRaises(TypeError, self.registry.register, C)


class IJSONSerializableTestCase(TestCase):

    def setUp(self):
        class C(IJSONSerializable):
            pass
        self.C = C

    def test_get_json_class_name(self):
        self.assertEqual(self.C._get_json_class_name(), 'C')

    def test_to_json(self):
        self.assertRaises(NotImplementedError, self.C().to_json)

    def test_from_json(self):
        self.assertRaises(NotImplementedError, self.C().from_json, '')


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


