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
from lava_server.settings.getsettings import Settings


class Command(BaseCommand):
    args = '<username>'
    help = 'Add given username from the configured LDAP server'

    def handle(self, *args, **options):
        if len(args) > 0:
            username = args[0]
        else:
            self.stderr.write("Username not specified")
            return

        settings = Settings("lava-server")
        server_uri = settings.get_setting("AUTH_LDAP_SERVER_URI", None)
        bind_dn = settings.get_setting("AUTH_LDAP_BIND_DN", None)
        bind_password = settings.get_setting("AUTH_LDAP_BIND_PASSWORD", None)
        user_dn_template = settings.get_setting("AUTH_LDAP_USER_DN_TEMPLATE",
                                                None)
        user_dn = user_dn_template % {'user': username}
        search_scope = ldap.SCOPE_SUBTREE
        attributes = ['uid', 'givenName', 'sn', 'mail']
        search_filter = "cn=*"

        if server_uri is not None:
            conn = ldap.initialize(server_uri)
            if bind_dn and bind_password:
                conn.simple_bind_s(bind_dn, bind_password)
                try:
                    result = conn.search_s(user_dn, search_scope,
                                           search_filter, attributes)
                    if len(result) == 1:
                        result_type, result_data = result[0]
                        uid = result_data.get('uid', [None])[0]
                        mail = result_data.get('mail', [None])[0]
                        sn = result_data.get('sn', [None])[0]
                        given_name = result_data.get('givenName', [None])[0]
                except ldap.NO_SUCH_OBJECT:
                    self.stderr.write("User %s does not exist in LDAP"
                                      % username)
                    return
                try:
                    user = User.objects.get(username=username)
                    self.stderr.write('User "%s" exists, not overwriting' %
                                      username)
                except User.DoesNotExist:
                    user = User.objects.create(username=username)
                    if mail:
                        user.email = mail
                    if sn:
                        user.last_name = sn
                    if given_name:
                        user.first_name = given_name
                    user.save()
                    self.stdout.write('User "%s" added' % username)
