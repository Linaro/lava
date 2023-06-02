# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import csv

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db.utils import IntegrityError

from linaro_django_xmlrpc.models import AuthToken


class Command(BaseCommand):
    help = "Manage tokens"

    def add_arguments(self, parser):
        sub = parser.add_subparsers(
            dest="sub_command",
            help="Sub commands",
        )
        sub.required = True

        add_parser = sub.add_parser("add", help="Create a token")
        add_parser.add_argument(
            "--user", "-u", type=str, required=True, help="The token owner"
        )
        add_parser.add_argument(
            "--description", "-d", type=str, default="", help="The token description"
        )
        add_parser.add_argument(
            "--secret", type=str, default=None, help="The token to import"
        )

        list_parser = sub.add_parser("list", help="List the tokens")
        list_parser.add_argument(
            "--user", "-u", type=str, required=True, help="The tokens owner"
        )
        list_parser.add_argument(
            "--csv", dest="csv", default=False, action="store_true", help="Print as csv"
        )

        del_parser = sub.add_parser("rm", help="Remove a token")
        del_parser.add_argument("token", type=str, help="The token to remove")

    def handle(self, *args, **options):
        """Forward to the right sub-handler"""
        if options["sub_command"] == "add":
            self.handle_add(options["user"], options["description"], options["secret"])
        elif options["sub_command"] == "list":
            self.handle_list(options["user"], options["csv"])
        else:
            self.handle_rm(options["token"])

    def handle_add(self, username, description, secret):
        """Create a token"""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError("Unable to find user '%s'" % username)
        if secret is None:
            token = AuthToken.objects.create(user=user, description=description)
        else:
            try:
                token = AuthToken.objects.create(
                    user=user, description=description, secret=secret
                )
            except IntegrityError:
                raise CommandError("Check that the token secret is not already used")
        self.stdout.write(token.secret)

    def handle_list(self, username, format_as_csv):
        """List the tokens for the given user"""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError("Unable to find user '%s'" % username)

        tokens = AuthToken.objects.filter(user=user).order_by("id")
        if format_as_csv:
            fields = ["id", "secret", "description"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for token in tokens:
                writer.writerow(
                    {
                        "id": token.id,
                        "secret": token.secret,
                        "description": token.description,
                    }
                )
        else:
            self.stdout.write("Tokens for user '%s':" % username)
            for token in tokens:
                self.stdout.write("* %s (%s)" % (token.secret, token.description))

    def handle_rm(self, token):
        """Remove the token, knowing the secret"""
        try:
            AuthToken.objects.get(secret=token).delete()
        except AuthToken.DoesNotExist:
            raise CommandError("Invalid token secret")
