# Copyright (C) 2013-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from datetime import timedelta  # pylint: disable=unused-import

import django_tables2 as tables
from django.conf import settings
from django.db.models import Q
from django.utils import timezone  # pylint: disable=unused-import
from django.utils.html import escape


class LavaView(tables.SingleTableView):
    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request

    def _time_filter(self, query):
        """
        bespoke time-based field handling
        """
        time_queries = {}
        if hasattr(self.table_class.Meta, "times"):
            # filter the possible list by the request
            for key, value in self.table_class.Meta.times.items():
                # check if the request includes the current time filter & get the value
                match = self.request.GET.get(key)
                if match and match != "":
                    # the label for this query in the search list
                    time_queries[key] = value
            for key, value in time_queries.items():
                match = escape(self.request.GET.get(key))
                # escape converts None into u'None'
                if not match or match == "" or match == "None":
                    continue

                query &= Q(
                    **{f"{key}__gte": timezone.now() - timedelta(**{value: int(match)})}
                )

        return query

    def get_table_data(self, prefix=None):
        """
        Takes the table data and adds filters based on the content of the request
        Needs to change each field into a text string, e.g. job.actual_device -> device.hostname
        - simple text search support:
          searches - simple text only fields which can be searched with case insensitive text matches
          queries - relational fields for which the table has explicit handlers for simple text searching
        - special knowledge of particular field types is handled as:
          times - fields which can be searched by a duration
        :return: filtered data
        """
        data = self.get_queryset()
        if not self.table_class or not hasattr(self.table_class, "Meta"):
            return data

        distinct = {}
        if hasattr(self.table_class.Meta, "searches"):
            for key in self.table_class.Meta.searches.keys():
                discrete_key = "%s%s" % (prefix, key) if prefix else key
                if self.request and self.request.GET.get(discrete_key):
                    distinct[discrete_key] = escape(self.request.GET.get(discrete_key))

        if hasattr(self.table_class.Meta, "queries"):
            for func, argument in self.table_class.Meta.queries.items():
                request_argument = "%s%s" % (prefix, argument) if prefix else argument
                if self.request and self.request.GET.get(request_argument):
                    distinct[func] = escape(self.request.GET.get(request_argument))
        if not self.request:
            return data

        q = Q()
        # discrete searches
        for key, val in distinct.items():
            if key in self.table_class.Meta.searches:
                q &= Q(**{f"{key}__contains": val})

            if (
                hasattr(self.table_class.Meta, "queries")
                and key in self.table_class.Meta.queries.keys()
            ):
                # note that this calls
                # the function 'key' with the argument from the search
                q &= getattr(self, key)(val)

        # general OR searches
        general_search = self.request.GET.get(f"{prefix}search" if prefix else "search")

        if general_search and hasattr(self.table_class.Meta, "searches"):
            for key, val in self.table_class.Meta.searches.items():
                # this is a little bit of magic - creates an OR clause
                # in the query based on the iterable search hash
                # passed in via the table_class
                # e.g. self.searches = {'id', 'contains'}
                # so every simple search column in the table
                # is queried at the same time with OR
                q |= Q(**{f"{key}__{val}": general_search})

            # call explicit handlers as simple text searches of relational fields.
            if hasattr(self.table_class.Meta, "queries"):
                for key in self.table_class.Meta.queries:
                    # note that this calls the function 'key'
                    # with the argument from the search
                    q |= getattr(self, key)(general_search)

        # now add "class specials" - from an iterable hash
        # datetime uses (start_time__lte=timezone.now()-timedelta(days=3)
        return data.filter(self._time_filter(q))


class LavaTable(tables.Table):
    """
    Base class for all django-tables2 support in LAVA
    Provides search wrapper support for single tables
    and tables using prefixes, as well as a default page length.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = kwargs.pop("request", None)
        if (
            self.request
            and self.request.user.is_authenticated
            and hasattr(self.request.user, "extendeduser")
            and self.request.user.extendeduser.table_length
        ):
            self.length = self.request.user.extendeduser.table_length
        else:
            self.length = settings.DEFAULT_TABLE_LENGTH
        self.empty_text = "No data available in table"

    class Meta:
        attrs = {"class": "table table-striped", "width": "100%"}
        template_name = "tables.html"
        per_page_field = "length"
