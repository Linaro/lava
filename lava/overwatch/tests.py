"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from lava.overwatch.models import Device 


class DeviceTests(TestCase):

    def test_get_overwatch_success(self):
        device = Device.objects.create(
            overwatch_driver='dummy')
        from lava.overwatch.drivers.dummy import DummyDriver
        driver = device.get_overwatch()
        self.assertTrue(isinstance(driver, DummyDriver))


class BaseOverwatchDriverTests(TestCase):

    def test_init_loads_json_config(self):
        from lava.overwatch.drivers import BaseOverwatchDriver
        class ExampleDriver(BaseOverwatchDriver):
            pass
        observed = ExampleDriver('{"foo": "bar"}')._config
        expected = {"foo": "bar"}
        self.assertEqual(observed, expected)

    def test_init_handles_empty_string_gracefully(self):
        from lava.overwatch.drivers import BaseOverwatchDriver
        class ExampleDriver(BaseOverwatchDriver):
            pass
        observed = ExampleDriver('')._config
        expected = None 
        self.assertEqual(observed, expected)

    def test_enumerate_interfaces(self):
        from lava.overwatch.drivers import BaseOverwatchDriver
        class ExampleDriver(BaseOverwatchDriver):
            def _get_interfaces(self):
                return {"foo": None, "bar": None}
        observed = sorted(ExampleDriver('').enumerate_interfaces())
        expected = ["bar", "foo"]
        self.assertEqual(observed, expected)

    def test_get_interface(self):
        from lava.overwatch.drivers import BaseOverwatchDriver
        class ExampleDriver(BaseOverwatchDriver):
            def _get_interfaces(self):
                return {"foo": lambda driver: driver} 
        driver = ExampleDriver('')
        observed = driver.get_interface("foo")
        expected = driver

    def test_get_interface_missing(self):
        from lava.overwatch.drivers import BaseOverwatchDriver
        class ExampleDriver(BaseOverwatchDriver):
            def _get_interfaces(self):
                return {}
        self.assertRaises(ValueError, ExampleDriver('').get_interface, "foo")


class BaseOverwatchInterfaceTests(TestCase):

    def test_get_name(self):
        from lava.overwatch.drivers import BaseOverwatchInterface
        class ExampleInterface(BaseOverwatchInterface):
            INTERFACE_NAME = "example"
        observed = ExampleInterface().get_name()
        expected = ExampleInterface.INTERFACE_NAME
        self.assertEqual(observed, expected)

    def test_enumerate_actions(self):
        from lava.overwatch.drivers import BaseOverwatchInterface
        from lava.overwatch.decorators import action 
        class ExampleInterface(BaseOverwatchInterface):
            @action
            def foo(self):
                pass
            @action
            def bar(self):
                pass
            def froz(self):
                pass
        observed = sorted(ExampleInterface().enumerate_actions())
        expected = ['bar', 'foo']
        self.assertEqual(observed, expected)

    def test_run_action(self):
        from lava.overwatch.drivers import BaseOverwatchInterface
        from lava.overwatch.decorators import action 
        class ExampleInterface(BaseOverwatchInterface):
            def __init__(self, test):
                self.test = test
            @action
            def foo(self):
                self.test.assertTrue(True)
        ExampleInterface(self).run_action("foo")
