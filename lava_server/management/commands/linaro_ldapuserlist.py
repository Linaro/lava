# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import csv
import os

import ldap
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# It is a very rarely used management command, hence many parameters are
# hardcoded here. This will change as per the LDAP configuration of different
# organizations. Following is a sample for Linaro LDAP server. Edit the
# following based on your organization's LDAP settings. Remember it also,
# depends on LDAP specific values in /etc/lava-server/settings.conf - revisit
# to ensure things are configured properly.
LDAP_SERVER_HOST = "login.linaro.org"
USER_DN = "ou=staff,ou=accounts,dc=linaro,dc=org"
SEARCH_SCOPE = ldap.SCOPE_SUBTREE
ATTRIBUTES = ["uid"]
SEARCH_FILTER = "cn=*"


def _get_script_path():
    """Get the path of current script."""
    file_path = ""
    try:
        file_path = __file__
        if file_path.endswith(".pyc") and os.path.exists(file_path[:-1]):
            file_path = file_path[:-1]
    except AttributeError:
        file_path = "linaro_ldapuserlist.py"

    return file_path


class Command(BaseCommand):
    help = (
        "Write complete ldap user list from "
        + LDAP_SERVER_HOST
        + " as CSV to the given filename."
    )

    def add_arguments(self, parser):
        parser.add_argument("--filename", type=str, help="Filename to write user list.")

    def handle(self, *args, **options):
        filename = options["filename"]
        if filename is None:
            self.stderr.write("filename not specified, writing to stdout.")

        server_uri = settings.AUTH_LDAP_SERVER_URI
        self.stdout.write("Trying to access %s ..." % server_uri)
        if LDAP_SERVER_HOST not in server_uri:
            raise CommandError(
                "This is a very rarely used management command, "
                "hence many parameters within this command are "
                "hardcoded. The best way to use this command is"
                " to copy and edit the python script '%s' to "
                "work with other LDAP systems." % _get_script_path()
            )

        bind_dn = settings.AUTH_LDAP_BIND_DN
        bind_password = settings.AUTH_LDAP_BIND_PASSWORD

        user_dn = USER_DN
        search_scope = SEARCH_SCOPE
        attributes = ATTRIBUTES
        search_filter = SEARCH_FILTER

        if server_uri is not None:
            conn = ldap.initialize(server_uri)
            if bind_dn and bind_password:
                conn.simple_bind_s(bind_dn, bind_password)
                results = conn.search_s(
                    user_dn, search_scope, search_filter, attributes
                )
                if filename:
                    with open(filename, "w") as csvfile:
                        file_handle = csv.writer(
                            csvfile,
                            delimiter=",",
                            quotechar="|",
                            quoting=csv.QUOTE_MINIMAL,
                        )
                        for result in results:
                            result_type, result_data = result
                            file_handle.writerow(
                                [result_data["uid"][0].decode("utf-8")]
                            )
                else:
                    for result in results:
                        result_type, result_data = result
                        self.stdout.write(result_data["uid"][0].decode("utf-8"))
                self.stdout.write('Total "%d" LDAP users' % len(results))
