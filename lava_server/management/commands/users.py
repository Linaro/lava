# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import csv

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Manage users"

    def add_arguments(self, parser):
        sub = parser.add_subparsers(
            dest="sub_command",
            help="Sub commands",
        )
        sub.required = True

        # "add" sub-command
        add_parser = sub.add_parser("add", help="Add a user")
        add_parser.add_argument("username", help="Username of the user")
        add_parser.add_argument(
            "--email", type=str, default=None, help="email of the user"
        )
        add_parser.add_argument(
            "--passwd",
            type=str,
            default=None,
            help="Password for this user. If empty, a random password is generated.",
        )
        add_parser.add_argument(
            "--staff",
            default=False,
            action="store_true",
            help="Make this user a staff member",
        )
        add_parser.add_argument(
            "--superuser",
            default=False,
            action="store_true",
            help="Make this user a super user",
        )

        # "update" sub-command
        update_parser = sub.add_parser("update", help="Update an existing user")
        update_parser.add_argument("username", help="Username of the user")
        update_parser.add_argument(
            "--email", type=str, default=None, help="Change email of the user"
        )

        active_parser = update_parser.add_mutually_exclusive_group(required=False)
        active_parser.add_argument(
            "--active",
            dest="active",
            action="store_const",
            const=True,  # not a boolean
            help="Make this user active",
        )
        active_parser.add_argument(
            "--not-active",
            dest="active",
            action="store_const",
            const=False,
            help="Make this user inactive",
        )
        active_parser.set_defaults(active=None)  # tri-state - None, True, False

        staff_parser = update_parser.add_mutually_exclusive_group(required=False)
        staff_parser.add_argument(
            "--staff",
            dest="staff",
            action="store_const",
            const=True,
            help="Make this user a staff member",
        )
        staff_parser.add_argument(
            "--not-staff",
            dest="staff",
            action="store_const",
            const=False,
            help="Make this user no longer a staff member",
        )
        staff_parser.set_defaults(staff=None)

        superuser_parser = update_parser.add_mutually_exclusive_group(required=False)
        superuser_parser.add_argument(
            "--superuser",
            dest="superuser",
            action="store_const",
            const=True,
            help="Make this user a superuser",
        )
        superuser_parser.add_argument(
            "--not-superuser",
            dest="superuser",
            action="store_const",
            const=False,
            help="Make this user no longer a superuser",
        )
        superuser_parser.set_defaults(superuser=None)

        # "details" sub-command
        details_parser = sub.add_parser("details", help="User details")
        details_parser.add_argument("username", help="Username of the user")

        # "list" sub-command
        list_parser = sub.add_parser("list", help="List users")
        list_parser.add_argument(
            "--all",
            dest="all",
            default=False,
            action="store_true",
            help="Show all users including inactive ones",
        )
        list_parser.add_argument(
            "--csv", dest="csv", default=False, action="store_true", help="Print as csv"
        )

    def handle(self, *args, **options):
        """Forward to the right sub-handler"""
        if options["sub_command"] == "add":
            self.handle_add(options)
        elif options["sub_command"] == "update":
            self.handle_update(options)
        elif options["sub_command"] == "details":
            self.handle_details(options["username"])
        elif options["sub_command"] == "list":
            self.handle_list(options["all"], options["csv"])

    def handle_add(self, options):
        """Create a new user"""
        username = options["username"]
        passwd = options["passwd"]
        if passwd is None:
            passwd = User.objects.make_random_password()
        user = User.objects.create_user(username, options["email"], passwd)

        if options["staff"]:
            user.is_staff = True
        if options["superuser"]:
            user.is_superuser = True
        user.save()

        if options["passwd"] is None:
            self.stdout.write(passwd)

    def handle_update(self, options):
        """Update existing user"""
        username = options["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError("User %s does not exist" % username)
        if options["email"]:
            user.email = options["email"]
        # False is an allowed value, but not None.
        if options["active"] in [True, False]:
            user.is_active = options["active"]
        if options["staff"] in [True, False]:
            user.is_staff = options["staff"]
        if options["superuser"] in [True, False]:
            user.is_superuser = options["superuser"]
        user.save()

    def handle_details(self, username):
        """Print user details"""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError("Unable to find user '%s'" % username)

        self.stdout.write("username    : %s" % username)
        self.stdout.write("is_active   : %s" % user.is_active)
        self.stdout.write("is_staff    : %s" % user.is_staff)
        self.stdout.write("is_superuser: %s" % user.is_superuser)
        groups = [g.name for g in user.groups.all().order_by("name")]
        self.stdout.write("groups      : [%s]" % ", ".join(groups))

    def handle_list(self, show_all, format_as_csv):
        """List users"""
        users = User.objects.all().order_by("username")
        if not show_all:
            users = users.exclude(is_active=False)

        if format_as_csv:
            fields = ["username", "fullname", "email", "staff", "superuser"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for user in users:
                writer.writerow(
                    {
                        "username": user.username,
                        "fullname": user.get_full_name(),
                        "email": user.email,
                        "staff": user.is_staff,
                        "superuser": user.is_superuser,
                    }
                )

        else:
            self.stdout.write("List of users:")
            for user in users:
                out = "* %s" % user.username

                if user.get_full_name():
                    out = "%s (%s)" % (out, user.get_full_name())
                if not user.is_active:
                    out = "%s [inactive]" % out

                self.stdout.write(out)
