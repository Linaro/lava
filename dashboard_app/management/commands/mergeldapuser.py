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


import ldap

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from dashboard_app.helpers import get_ldap_user_properties


class Command(BaseCommand):
    args = '<lava_user> <ldap_user>'
    help = 'Merge given ldap_user with lava_user'

    def handle(self, *args, **options):
        if len(args) > 1:
            lava_user = old_lava_user = args[0]
            ldap_user = args[1]
        else:
            self.stderr.write("<lava_user> <ldap_user> are required")
            return
        try:
            ldap_user = User.objects.get(username=ldap_user)
            if ldap_user:
                self.stderr.write('LAVA user with the same ldap username ie., '
                                  '"%s", already exists, hence cannot merge' %
                                  ldap_user)
                return
        except User.DoesNotExist:
            self.stdout.write('LDAP user "%s", unavailable in LAVA, proceeding'
                              ' with the merge ...' % ldap_user)

        try:
            user_properties = get_ldap_user_properties(ldap_user)
            if user_properties is None:
                self.stderr.write('LDAP user "%s" properties incomplete'
                                  % ldap_user)
                return
        except ldap.NO_SUCH_OBJECT:
            self.stderr.write("User %s does not exist in LDAP" % ldap_user)
            return
        try:
            lava_user = User.objects.get(username=lava_user)
            lava_user.username = ldap_user
            lava_user.email = user_properties.get("mail", "")
            lava_user.last_name = user_properties.get("sn", "")
            lava_user.first_name = user_properties.get("given_name", "")
            lava_user.save()
            self.stdout.write('User "%s" merged with "%s"' % (ldap_user,
                                                              old_lava_user))
        except User.DoesNotExist:
            self.stderr.write('User "%s" does not exist in LAVA' % lava_user)
