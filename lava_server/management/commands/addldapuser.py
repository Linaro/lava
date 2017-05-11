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
import ldap

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from dashboard_app.helpers import get_ldap_user_properties


class Command(BaseCommand):
    help = 'Add given username from the configured LDAP server.'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str,
                            help='Username to be added.')
        parser.add_argument('--superuser', action='store_true',
                            dest='superuser', default=False,
                            help='User added will be made as superuser.')

    def handle(self, *args, **options):
        username = options['username']
        if username is None:
            self.stderr.write("Username not specified.")
            sys.exit(2)

        try:
            user_properties = get_ldap_user_properties(username)
            if user_properties is None:
                self.stderr.write('LDAP user "%s" properties incomplete'
                                  % username)
                return
        except ldap.NO_SUCH_OBJECT:
            self.stderr.write("User %s does not exist in LDAP" % username)
            return

        try:
            user = User.objects.get(username=username)
            self.stderr.write('User "%s" exists, not overwriting' % username)
        except User.DoesNotExist:
            user = User.objects.create(username=username)
            user.email = user_properties.get("mail", "")
            user.last_name = user_properties.get("sn", "")
            user.first_name = user_properties.get("given_name", "")
            superuser_msg = ""
            if options["superuser"]:
                user.is_staff = True
                user.is_superuser = True
                superuser_msg = "with superuser status"
            user.save()
            self.stdout.write('User "%s" added %s' % (username, superuser_msg))
