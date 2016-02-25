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


import os
import csv
import ldap

from lava_server.utils import OptArgBaseCommand as BaseCommand
from lava_server.settings.getsettings import Settings


# It is a very rarely used management command, hence many parameters are
# hardcoded here. This will change as per the LDAP configuration of different
# organizations. Following is a sample for Linaro LDAP server. Edit the
# following based on your organization's LDAP settings. Remember it also,
# depends on LDAP specific values in /etc/lava-server/settings.conf - revisit
# to ensure things are configured properly.
LDAP_SERVER_HOST = 'login.linaro.org'
USER_DN = 'ou=staff,ou=accounts,dc=linaro,dc=org'
SEARCH_SCOPE = ldap.SCOPE_SUBTREE
ATTRIBUTES = ['uid']
SEARCH_FILTER = 'cn=*'


def _get_script_path():
    """Get the path of current script.
    """
    file_path = ""
    try:
        file_path = __file__
        if file_path.endswith('.pyc') and os.path.exists(file_path[:-1]):
            file_path = file_path[:-1]
    except AttributeError:
        file_path = 'linaro_ldapuserlist.py'

    return file_path


class Command(BaseCommand):
    help = 'Write complete ldap user list from ' + LDAP_SERVER_HOST + \
           ' as CSV to the given filename.'

    def add_arguments(self, parser):
        parser.add_argument('--filename', type=str,
                            help='Filename to write user list.')

    def handle(self, *args, **options):
        filename = options['filename']
        if filename is None:
            self.stderr.write("filename not specified, writing to stdout.")

        settings = Settings("lava-server")
        server_uri = settings.get_setting("AUTH_LDAP_SERVER_URI", None)
        self.stdout.write("Trying to access %s ..." % server_uri)
        if LDAP_SERVER_HOST not in server_uri:
            self.stderr.write("This is a very rarely used management command, "
                              "hence many parameters within this command are "
                              "harcoded. The best way to use this command is"
                              " to copy and edit the python script '%s' to "
                              "work with other LDAP systems."
                              % _get_script_path())
            sys.exit(1)
        bind_dn = settings.get_setting("AUTH_LDAP_BIND_DN", None)
        bind_password = settings.get_setting("AUTH_LDAP_BIND_PASSWORD", None)

        user_dn = USER_DN
        search_scope = SEARCH_SCOPE
        attributes = ATTRIBUTES
        search_filter = SEARCH_FILTER

        if server_uri is not None:
            conn = ldap.initialize(server_uri)
            if bind_dn and bind_password:
                conn.simple_bind_s(bind_dn, bind_password)
                results = conn.search_s(user_dn, search_scope, search_filter,
                                        attributes)
                if filename:
                    with open(filename, 'wb') as csvfile:
                        file_handle = csv.writer(csvfile, delimiter=',',
                                                 quotechar='|',
                                                 quoting=csv.QUOTE_MINIMAL)
                        for result in results:
                            result_type, result_data = result
                            file_handle.writerow([result_data['uid'][0]])
                else:
                    for result in results:
                        result_type, result_data = result
                        self.stdout.write(result_data['uid'][0])
                self.stdout.write('Total "%d" LDAP users' % len(results))
