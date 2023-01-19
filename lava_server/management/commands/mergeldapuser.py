# -*- coding: utf-8 -*-
# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import ldap
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import truncatechars

from lava_scheduler_app.utils import get_ldap_user_properties


class Command(BaseCommand):
    help = "Merge given LDAP_USER with LAVA_USER"

    def add_arguments(self, parser):
        parser.add_argument("--lava-user", help="LAVA username.")
        parser.add_argument("--ldap-user", help="LDAP username.")

    def handle(self, *args, **options):
        lava_user = old_lava_user = options["lava_user"]
        if lava_user is None:
            raise CommandError("LAVA username not specified.")

        ldap_user = options["ldap_user"]
        if ldap_user is None:
            raise CommandError("LDAP username not specified.")

        try:
            ldap_user = User.objects.get(username=ldap_user)
            if ldap_user:
                self.stderr.write(
                    "LAVA user with the same ldap username ie., "
                    '"%s", already exists, hence cannot merge' % ldap_user
                )
                return
        except User.DoesNotExist:
            self.stdout.write(
                'LDAP user "%s", unavailable in LAVA, proceeding'
                " with the merge ..." % ldap_user
            )

        try:
            user_properties = get_ldap_user_properties(ldap_user)
            if user_properties is None:
                self.stderr.write('LDAP user "%s" properties incomplete' % ldap_user)
                return
        except ldap.NO_SUCH_OBJECT:
            self.stderr.write("User %s does not exist in LDAP" % ldap_user)
            return
        try:
            lava_user = User.objects.get(username=lava_user)
            lava_user.username = ldap_user
            lava_user.email = user_properties.get("mail", "")
            # Grab max_length and truncate first and last name.
            # For some users, the command fail as first or last name is too long.
            first_name_max_length = User._meta.get_field("first_name").max_length
            last_name_max_length = User._meta.get_field("last_name").max_length
            lava_user.last_name = truncatechars(
                user_properties.get("sn", ""), last_name_max_length
            )
            lava_user.first_name = truncatechars(
                user_properties.get("given_name", ""), first_name_max_length
            )
            lava_user.save()
            self.stdout.write('User "%s" merged with "%s"' % (ldap_user, old_lava_user))
        except User.DoesNotExist:
            self.stderr.write('User "%s" does not exist in LAVA' % lava_user)
