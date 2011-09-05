#!/usr/bin/env python
#
# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import pkg_resources
import argparse

from lava_tool.dispatcher import LavaDispatcher, run_with_dispatcher_class
from lava_tool.interface import Command


class LAVAServerDispatcher(LavaDispatcher):

    toolname = 'lava_server'
    description = """
    LAVA Application Server
    """
    epilog = """
    Please report all bugs using the Launchpad bug tracker:
    http://bugs.launchpad.net/lava-server/+filebug
    """

    def __init__(self):
        # XXX The below needs to allow some customization.
        parser_args = dict(add_help=False)
        if self.description is not None:
            parser_args['description'] = self.description
        if self.epilog is not None:
            parser_args['epilog'] = self.epilog
        self.parser = argparse.ArgumentParser(**parser_args)
        self.subparsers = self.parser.add_subparsers(
                title="Sub-command to invoke")
        prefixes = []
        if self.toolname is not None:
            prefixes.append(self.toolname)
        for prefix in prefixes:
            for entrypoint in pkg_resources.iter_entry_points(
                "%s.commands" % prefix):
                self.add_command_cls(entrypoint.load())


class manage(Command):
    """
    Manage the LAVA server
    """

    @classmethod
    def register_arguments(cls, parser):
        parser.add_argument("-p", "--production",
                            action="store_true",
                            default=False,
                            help="Use production settings")
        parser.add_argument("-i", "--instance",
                            action="store",
                            default=None,
                            help="Use the specified instance (works only with --production)")
        parser.add_argument("command", nargs="...",
                            help="Invoke this Django management command")

    def invoke(self):
        settings_module = "lava_server.settings.development"
        if self.args.production:
            settings_module = "lava_server.settings.debian"
        if self.args.instance:
            if not os.path.isdir(self.args.instance):
                self.parser.error("Specified instance does not exsit")
            os.environ["DJANGO_DEBIAN_SETTINGS_TEMPLATE"] = self.args.instance + "/etc/{filename}.conf"
        settings = __import__(settings_module, fromlist=[''])
        from django.core.management import execute_manager
        execute_manager(settings, ['lava-server'] + self.args.command)


def find_sources():
    base_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..")
    if os.path.exists(os.path.join(base_path, "lava_server")):
        sys.path.insert(0, base_path)


def main():
    find_sources()
    run_with_dispatcher_class(LAVAServerDispatcher)
