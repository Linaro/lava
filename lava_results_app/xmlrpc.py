# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

import xmlrpclib
from linaro_django_xmlrpc.models import ExposedAPI

from lava_results_app.models import (
    Query,
    RefreshLiveQueryError
)


class ResultsAPI(ExposedAPI):

    def refresh_query(self, query_name, username=None):
        """
        Name
        ----
        `refresh_query` (`query_name`, `username`)

        Description
        -----------
        Refreshes the query with the given name owned by specific user.

        Arguments
        ---------
        `query_name`: string
            Query name string.
        `username`: string
            Username of the user which is owner of/created the query you would
            like to update. Defaults to None, in which case the method will
            consider the authenticated user to be the owner.
            Either way, the authenticated user needs to have special access to
            this query (being an owner or belonging to the group which has
            admin access to the query).

        Return value
        ------------
        None. The user should be authenticated with a username and token.
        """
        self._authenticate()
        if not username:
            username = self.user.username

        try:
            query = Query.objects.get(name=query_name,
                                      owner__username=username)
        except Query.DoesNotExist:
            raise xmlrpclib.Fault(
                400, "Query with name %s owned by user %s does not exist." %
                (query_name, username))

        if not query.is_accessible_by(self.user):
            raise xmlrpclib.Fault(
                401, "Permission denied for user to query %s" % query_name)

        query.refresh_view()

    def refresh_all_queries(self):
        """
        Name
        ----
        `refresh_all_queries`

        Description
        -----------
        Refreshes all queries in the system. Available only for superusers.

        Arguments
        ---------
        None.

        Return value
        ------------
        None. The user should be authenticated with a username and token.
        """
        self._authenticate()

        if not self.user.is_superuser:
            raise xmlrpclib.Fault(
                401, "Permission denied for user %s. Must be a superuser to "
                "refresh all queries." % self.user.username)

        for query in Query.objects.all():
            try:
                query.refresh_view()
            except RefreshLiveQueryError:
                pass
