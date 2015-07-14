# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# This file is part of LAVA Dashboard
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


import sys

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    args = '<username>'
    help = 'Authorise superuser'

    def handle(self, *args, **options):
        if len(args) > 0:
            username = args[0]
        else:
            self.stderr.write("Username not specified")
            sys.exit(2)

        try:
            user = User.objects.get(username=username)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write('User "%s" granted superuser rights' % username)
        except User.DoesNotExist:
            self.stderr.write('User "%s" does not exist' % username)
