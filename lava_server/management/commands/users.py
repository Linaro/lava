# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import csv

from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser
)

from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Manage users"

    def add_arguments(self, parser):
        cmd = self

        class SubParser(CommandParser):
            """
            Sub-parsers constructor that mimic Django constructor.
            See http://stackoverflow.com/a/37414551
            """
            def __init__(self, **kwargs):
                super(SubParser, self).__init__(cmd, **kwargs)

        sub = parser.add_subparsers(dest="sub_command", help="Sub commands", parser_class=SubParser)

        # "add" sub-command
        add_parser = sub.add_parser("add", help="Add a device")
        add_parser.add_argument("username",
                                help="Username of the user")
        add_parser.add_argument("--email", type=str, default=None,
                                help="email of the user")
        add_parser.add_argument("--passwd", type=str, default=None,
                                help="Password for this user. If empty, a random password is generated.")
        add_parser.add_argument("--staff", default=False,
                                action="store_true",
                                help="Make this user a staff member")
        add_parser.add_argument("--superuser", default=False,
                                action="store_true",
                                help="Make this user a super user")

        # "details" sub-command
        details_parser = sub.add_parser("details", help="Device details")
        details_parser.add_argument("username",
                                    help="Username of the user")

        # "list" sub-command
        list_parser = sub.add_parser("list", help="List devices")
        list_parser.add_argument("--all", dest="all", default=False,
                                 action="store_true",
                                 help="Show all users including inactive ones")
        list_parser.add_argument("--csv", dest="csv", default=False,
                                 action="store_true", help="Print as csv")

    def handle(self, *args, **options):
        """ Forward to the right sub-handler """
        if options["sub_command"] == "add":
            self.handle_add(options)
        elif options["sub_command"] == "details":
            self.handle_details(options['username'])
        elif options["sub_command"] == "list":
            self.handle_list(options["all"], options["csv"])

    def handle_add(self, options):
        """ Create a new user """
        username = options['username']
        passwd = options['passwd']
        if passwd is None:
            passwd = User.objects.make_random_password()
        user = User.objects.create_user(username, options['email'],
                                        passwd)

        if options['staff']:
            user.is_staff = True
        if options['superuser']:
            user.is_superuser = True
        user.save()

        if options['passwd'] is None:
            self.stdout.write(passwd)

    def handle_details(self, username):
        """ Print user details """
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError("Unable to find user '%s'" % username)

        self.stdout.write("username    : %s" % username)
        self.stdout.write("is_active   : %s" % user.is_active)
        self.stdout.write("is_staff    : %s" % user.is_staff)
        self.stdout.write("is_superuser: %s" % user.is_superuser)
        groups = [g.name for g in user.groups.all().order_by('name')]
        self.stdout.write("groups      : [%s]" % ", ".join(groups))

    def handle_list(self, show_all, format_as_csv):
        """ List users """
        users = User.objects.all().order_by('username')
        if not show_all:
            users = users.exclude(is_active=False)

        if format_as_csv:
            fields = ["username", "fullname", "email", "staff", "superuser"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for user in users:
                writer.writerow({
                    "username": user.username,
                    "email": user.email,
                    "staff": user.is_staff,
                    "superuser": user.is_superuser})

        else:
            self.stdout.write("List of users:")
            for user in users:
                out = "* %s" % user.username

                if user.get_full_name():
                    out = "%s (%s)" % (out, user.get_full_name())
                if not user.is_active:
                    out = "%s [inactive]" % out

                self.stdout.write(out)
