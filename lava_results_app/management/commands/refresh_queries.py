# Copyright (C) 2016 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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


import sys
from django.core.management.base import BaseCommand
from lava_results_app.models import Query


class Command(BaseCommand):
    """
    Provide lava-server manage access to refresh_query
    and refresh_all_queries
    """

    logger = None

    def __init__(self, *args, **options):
        super(Command, self).__init__(*args, **options)
        self.help = "LAVA V2 query helper"

    def add_arguments(self, parser):
        parser.add_argument('--name', help="Name of the query")
        parser.add_argument('--username', help="Username for named query")
        parser.add_argument('--all', dest='all', action='store_true', help='Refresh all queries')

    def handle(self, *args, **options):
        if not options['name'] and not options['all']:
            self.stderr.write("Please specify a query or use --all")
            sys.exit(2)
        query_name = options['name']
        if query_name:
            if not options['username']:
                self.stderr.write("Named queries need a username to make a unique match.")
                sys.exit(2)
            try:
                query = Query.objects.get(name=query_name, is_live=False, owner__username=options['username'])
            except Query.DoesNotExist:
                self.stderr.write(
                    "Error: A cached query with name %s does not exist for user %s." % (
                        query_name, options['username']))
                sys.exit(1)
            query.refresh_view()
        else:
            for query in Query.objects.all().filter(is_live=False):
                query.refresh_view()
