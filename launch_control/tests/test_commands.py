"""
Unit tests for the launch_control.commands package
"""

from unittest import TestCase

from launch_control.commands.interface import Command
from launch_control.commands.dispatcher import (
        LaunchControlDispatcher,
        main,
        )
from launch_control.thirdparty.mocker import (
        ANY,
        MockerTestCase,
        expect,
        )


class CommandTestCase(TestCase):

    def test_not_implemented(self):
        self.assertRaises(NotImplementedError, Command(None, None).invoke)

    def test_get_name_uses_class_name(self):
        class Foo(Command):
            pass
        self.assertEqual(Foo.get_name(), "Foo")

    def test_get_name_strips_leading_underscore(self):
        class _Bar(Command):
            pass
        self.assertEqual(_Bar.get_name(), "Bar")

    def test_get_name_converts_underscore_to_dash(self):
        class froz_bot(Command):
            pass
        self.assertEqual(froz_bot.get_name(), "froz-bot")

    def test_get_help_uses_docstring(self):
        class ASDF(Command):
            """
            This command was named after the lisp package management system
            """
        self.assertEqual(ASDF.get_help(), 'This command was named after the lisp package management system')

    def test_get_help_defaults_to_None(self):
        class mysterious(Command): pass
        self.assertEqual(mysterious.get_help(), None)


class DispatcherTestCase(MockerTestCase):
    
    def test_command_registration(self):
        TestCmd = self.mocker.mock()
        Command = self.mocker.replace('launch_control.commands.interface.Command')
        expect(Command.get_subclasses()).result([TestCmd])
        expect(TestCmd.get_name()).result("TestCmd")
        expect(TestCmd.get_help()).result("test command")
        expect(TestCmd.register_arguments(ANY))
        self.mocker.replay()
        lcd = LaunchControlDispatcher()

    def test_command_dispatch(self):
        TestCmd = self.mocker.mock()
        test_cmd_obj = self.mocker.mock()
        Command = self.mocker.replace('launch_control.commands.interface.Command')
        expect(Command.get_subclasses()).result([TestCmd])
        expect(TestCmd.get_name()).result("TestCmd")
        expect(TestCmd.get_help()).result("test command")
        expect(TestCmd.register_arguments(ANY))
        expect(TestCmd(ANY, ANY)).result(test_cmd_obj)
        expect(test_cmd_obj.invoke())
        self.mocker.replay()
        lcd = LaunchControlDispatcher()
        lcd.dispatch(["TestCmd"])

    def test_main(self):
        LaunchControlDispatcher = self.mocker.replace('launch_control.commands.dispatcher.LaunchControlDispatcher')
        LaunchControlDispatcher().dispatch()
        self.mocker.replay()
        main()
