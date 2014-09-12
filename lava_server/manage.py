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
    Please report all bugs using the Linaro bug tracker:
    https://bugs.linaro.org/enter_bug.cgi?product=LAVA%20Framework
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
        group = parser.add_argument_group("Server configuration")
        group.add_argument(
            "-d", "--development",
            action="store_false",
            dest="production",
            help="Use development settings")
        group.add_argument(
            "-p", "--production",
            action="store_true",
            default=True,
            help="Use production settings (default)")
        try:
            instance_name = os.environ["LAVA_INSTANCE"]
        except KeyError:
            try:
                instance_name = os.path.basename(os.environ["VIRTUAL_ENV"])
            except KeyError:
                instance_name = None
        group.add_argument(
            "-i", "--instance",
            action="store",
            default=instance_name,
            help="Use the specified instance (works only with --production, default %(default)s)")
        group.add_argument(
            "-I", "--instance-template",
            action="store",
            default=(
                "/srv/lava/instances/{instance}"
                "/etc/lava-server/{{filename}}.conf"),
            help=(
                "Template used for constructing instance pathname."
                " The default value is: %(default)s"))
        parser.add_argument(
            "command", nargs="...",
            help="Invoke this Django management command")

    def invoke(self):
        if self.args.production:
            settings_module = "lava_server.settings.distro"
        else:
            settings_module = "lava_server.settings.development"
        if self.args.instance:
            ddst = self.args.instance_template.format(
                instance=self.args.instance)
            os.environ["DJANGO_DEBIAN_SETTINGS_TEMPLATE"] = ddst
        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
        from django.core.management import execute_from_command_line
        execute_from_command_line(['lava-server'] + self.args.command)


def find_sources():
    base_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..")
    if os.path.exists(os.path.join(base_path, "lava_server")):
        sys.path.insert(0, base_path)


def main():
    run_with_dispatcher_class(LAVAServerDispatcher)


def legacy_main():
    find_sources()
    settings_module = "lava_server.settings.development"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    legacy_main()
