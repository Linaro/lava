# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Unit tests for the launch_control.commands package
"""

from unittest import TestCase

from launch_control.commands.interface import Command
from launch_control.commands.dispatcher import (
        LaunchControlDispatcher,
        main,
        )
from launch_control.commands.dashboard import (
        XMLRPCCommand,
        )
from launch_control.thirdparty.mocker import (
        ANY,
        MockerTestCase,
        expect,
        )


class CommandTestCase(MockerTestCase):

    def test_register_arguments_does_nothing(self):
        parser = self.mocker.mock()
        self.mocker.replay()
        Command.register_arguments(parser)

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
        expect(TestCmd.__abstract__).result(False)
        expect(TestCmd.get_name()).result("TestCmd")
        expect(TestCmd.get_help()).result("test command")
        expect(TestCmd.register_arguments(ANY))
        self.mocker.replay()
        lcd = LaunchControlDispatcher()

    def test_command_registration_skips_abstract_classes(self):
        TestCmd = self.mocker.mock()
        Command = self.mocker.replace('launch_control.commands.interface.Command')
        expect(Command.get_subclasses()).result([TestCmd])
        expect(TestCmd.__abstract__).result(True)
        self.mocker.replay()
        lcd = LaunchControlDispatcher()

    def test_command_dispatch(self):
        TestCmd = self.mocker.mock()
        test_cmd_obj = self.mocker.mock()
        Command = self.mocker.replace('launch_control.commands.interface.Command')
        expect(Command.get_subclasses()).result([TestCmd])
        expect(TestCmd.__abstract__).result(False)
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
        self.assertRaises(SystemExit, main)


class XMLRPCCommandTestCase(TestCase):

    def test_construct_xml_rpc_url_preserves_path(self):
        self.assertEqual(
            XMLRPCCommand._construct_xml_rpc_url("http://domain/path"),
            "http://domain/path/xml-rpc/")
        self.assertEqual(
            XMLRPCCommand._construct_xml_rpc_url("http://domain/path/"),
            "http://domain/path/xml-rpc/")

    def test_construct_xml_rpc_url_adds_proper_suffix(self):
        self.assertEqual(
            XMLRPCCommand._construct_xml_rpc_url("http://domain/"),
            "http://domain/xml-rpc/")
        self.assertEqual(
            XMLRPCCommand._construct_xml_rpc_url("http://domain"),
            "http://domain/xml-rpc/")
