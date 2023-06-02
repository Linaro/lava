# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Authorize superuser."

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, help="Username to authorize.")

    def handle(self, *args, **options):
        username = options["username"]
        if username is None:
            raise CommandError("Username not specified.")

        try:
            user = User.objects.get(username=username)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write('User "%s" granted superuser rights' % username)
        except User.DoesNotExist:
            self.stderr.write('User "%s" does not exist' % username)
