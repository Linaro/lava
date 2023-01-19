# -*- coding: utf-8 -*-
# Copyright (C) 2016-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

import sys

from django.core.management.base import BaseCommand

from lava_results_app.models import Query, QueryUpdatedError, RefreshLiveQueryError


class Command(BaseCommand):
    """
    Provide lava-server manage access to refresh_query
    and refresh_all_queries
    """

    logger = None
    help = "LAVA V2 query helper"

    def add_arguments(self, parser):
        parser.add_argument("--name", help="Name of the query")
        parser.add_argument("--username", help="Username for named query")
        parser.add_argument(
            "--all", dest="all", action="store_true", help="Refresh all queries"
        )

    def handle(self, *args, **options):
        if not options["name"] and not options["all"]:
            self.stderr.write("Please specify a query or use --all")
            sys.exit(2)
        query_name = options["name"]
        if query_name:
            if not options["username"]:
                self.stderr.write(
                    "Named queries need a username to make a unique match."
                )
                sys.exit(2)
            try:
                query = Query.objects.get(
                    name=query_name, owner__username=options["username"]
                )
            except Query.DoesNotExist:
                self.stderr.write(
                    "Error: Query with name %s does not exist for user %s."
                    % (query_name, options["username"])
                )
                sys.exit(1)
            self._refresh_query(query)
        else:
            for query in Query.objects.all().filter(is_live=False, is_archived=False):
                self._refresh_query(query)

    def _refresh_query(self, query):
        if query.is_archived:
            self.stderr.write(
                "Query with name %s owned by user %s is archived."
                % (query.name, query.owner.username)
            )
            return
        try:
            query.refresh_view()
        except QueryUpdatedError as e:
            self.stderr.write(
                "Query with name %s owned by user %s was recently refreshed."
                % (query.name, query.owner.username)
            )
        except RefreshLiveQueryError as e:
            self.stderr.write(
                "Query with name %s owned by user %s cannot be refreshed since it's a live query."
                % (query.name, query.owner.username)
            )
        except Exception as e:
            self.stderr.write(
                "Refresh operation for query with name %s owned by user %s failed: %s"
                % (query.name, query.owner.username, str(e))
            )
