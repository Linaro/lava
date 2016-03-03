# Copyright (C) 2016 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# This file is part of LAVA Server
#
# Lava Dashboard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Dashboard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard. If not, see <http://www.gnu.org/licenses/>.


import django
from optparse import make_option
from django.core.management.base import BaseCommand


class ArgOptParser(object):
    """Changes arguments into options."""

    def __init__(self, command):
        self.command = command

    def add_argument(self, *args, **options):
        self.command.option_list += (make_option(*args, **options), )


class OptArgBaseCommand(BaseCommand):
    """Changes optparse to argparse."""

    def __init__(self, *args, **options):
        if django.VERSION < (1, 8) and hasattr(self, 'add_arguments'):
            self.option_list = BaseCommand.option_list
            parser = ArgOptParser(self)
            self.add_arguments(parser)
        super(OptArgBaseCommand, self).__init__(*args, **options)

    def handle(self, *args, **options):
        raise NotImplementedError
