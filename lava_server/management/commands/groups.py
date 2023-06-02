# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from django.contrib.auth.models import Group, Permission, User
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
        add_parser = sub.add_parser("add", help="Add a group")
        add_parser.add_argument("name", help="Name of the Django group")
        add_parser.add_argument(
            "--username",
            default=None,
            dest="username",
            help="Username of a user to add to the new group",
        )
        add_parser.add_argument(
            "--submitting",
            default=False,
            action="store_true",
            dest="submitting",
            help="Give users in this group permission to submit test jobs.",
        )

        # "update" sub-command
        update_parser = sub.add_parser("update", help="Update a group")
        update_parser.add_argument("name", help="Name of the Django group")
        update_parser.add_argument(
            "--username", dest="username", help="Username of a user to add to the group"
        )
        update_parser.add_argument(
            "--submitting",
            default=False,
            dest="submitting",
            action="store_true",
            help="Give users in this group permission to submit test jobs.",
        )

        # "list" sub-command
        list_parser = sub.add_parser("list", help="List groups")
        list_parser.add_argument(
            "--verbose",
            dest="verbose",
            default=False,
            action="store_true",
            help="Show all permissions for listed groups.",
        )

    def handle(self, *args, **options):
        """Forward to the right sub-handler"""
        if options["sub_command"] == "add":
            self.handle_add(options)
        if options["sub_command"] == "update":
            self.handle_update(options)
        elif options["sub_command"] == "list":
            self.handle_list(options["verbose"])

    def handle_update(self, options):
        """Update an existing group"""
        name = options["name"]
        group, created = Group.objects.get_or_create(name=name)
        if created:
            raise CommandError("Group '%s' does not already exist!" % name)
        submit = Permission.objects.filter(name="Can cancel or resubmit test jobs")
        if options["username"]:
            try:
                user = User.objects.get(username=options["username"])
            except User.DoesNotExist:
                raise CommandError("Unable to find user '%s'" % name)
            print("Adding user '%s' to group '%s'" % (user.username, group.name))
            group.user_set.add(user)
        if options["submitting"]:
            for perm in submit:
                print("Adding permission %s to group %s" % (perm, group.name))
                group.permissions.add(perm)

    def handle_add(self, options):
        """Create a new group"""
        name = options["name"]
        group, created = Group.objects.get_or_create(name=name)
        if not created:
            raise CommandError("Group '%s' already exists!" % name)

        submit = Permission.objects.filter(name="Can cancel or resubmit test jobs")
        if options["username"]:
            try:
                user = User.objects.get(username=options["username"])
            except User.DoesNotExist:
                raise CommandError("Unable to find user '%s'" % name)
            print("Adding user '%s' to group '%s'" % (user.username, group.name))
            group.user_set.add(user)
        if options["submitting"]:
            for perm in submit:
                print("Adding permission %s to group %s" % (perm, group.name))
                group.permissions.add(perm)

    def handle_list(self, verbose=False):
        """List groups with permissions"""
        groups = Group.objects.all().order_by("name")

        self.stdout.write("List of groups:")
        for group in groups:
            out = "* %s" % group.name
            if verbose:
                out = "%s (%s)" % (out, [perm.name for perm in group.permissions.all()])
            self.stdout.write(out)
