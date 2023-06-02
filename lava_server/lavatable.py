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
        self.terms = {}  # complete search term list, passed back to the template.
        self.search = []
        self.times = []
        self.discrete = []

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
                    self.terms[key] = f"{key} within {match} {value}"
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
        distinct = {}
        data = self.get_queryset()
        if not self.table_class or not hasattr(self.table_class, "Meta"):
            return data
        if prefix:
            table_search = "%ssearch" % prefix
        else:
            table_search = "search"
        if hasattr(self.table_class.Meta, "queries"):
            self.search.extend(self.table_class.Meta.queries.values())
            self.search.sort()
        if hasattr(self.table_class.Meta, "times"):
            for key, value in self.table_class.Meta.times.items():
                field = next(f for f in self.model._meta.get_fields() if f.name == key)
                column = self.table_class.base_columns.get(key)
                if (
                    column
                    and hasattr(column, "verbose_name")
                    and column.verbose_name is not None
                ):
                    self.times.append("%s (%s)" % (str(column.verbose_name), value))
                elif (
                    field
                    and hasattr(field, "verbose_name")
                    and field.verbose_name is not None
                ):
                    self.times.append("%s (%s)" % (str(field.verbose_name), value))
                else:
                    self.times.append("%s (%s)" % (key, value))
            self.times.sort()
        if hasattr(self.table_class.Meta, "searches"):
            for key in self.table_class.Meta.searches.keys():
                field = next(f for f in self.model._meta.get_fields() if f.name == key)
                column = self.table_class.base_columns.get(key)
                if (
                    column
                    and hasattr(column, "verbose_name")
                    and column.verbose_name is not None
                ):
                    self.search.append(column.verbose_name)
                elif field and hasattr(field, "verbose_name"):
                    self.search.append(field.verbose_name)
                else:
                    self.search.append(field)
                discrete_key = "%s%s" % (prefix, key) if prefix else key
                self.discrete.append(discrete_key)
                if self.request and self.request.GET.get(discrete_key):
                    distinct[discrete_key] = escape(self.request.GET.get(discrete_key))
            self.search = sorted(self.search, key=lambda s: s.lower())
        if hasattr(self.table_class.Meta, "queries"):
            for func, argument in self.table_class.Meta.queries.items():
                request_argument = "%s%s" % (prefix, argument) if prefix else argument
                self.discrete.append(request_argument)  # for __and__ queries
                if self.request and self.request.GET.get(request_argument):
                    distinct[func] = escape(self.request.GET.get(request_argument))
            self.discrete = sorted(self.discrete, key=lambda s: s.lower())
        if not self.request:
            return data

        q = Q()
        self.terms = {}
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
        if self.request.GET.get(table_search):
            self.terms["search"] = escape(self.request.GET.get(table_search))
        if hasattr(self.table_class.Meta, "searches") and "search" in self.terms:
            for key, val in self.table_class.Meta.searches.items():
                # this is a little bit of magic - creates an OR clause
                # in the query based on the iterable search hash
                # passed in via the table_class
                # e.g. self.searches = {'id', 'contains'}
                # so every simple search column in the table
                # is queried at the same time with OR
                q |= Q(**{f"{key}__{val}": self.terms["search"]})

            # call explicit handlers as simple text searches of relational fields.
            if hasattr(self.table_class.Meta, "queries"):
                for key in self.table_class.Meta.queries:
                    # note that this calls the function 'key'
                    # with the argument from the search
                    q |= getattr(self, key)(self.terms["search"])

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

    def prepare_search_data(self, data):
        if not hasattr(data, "search"):
            return {}
        if self.prefix:
            return {self.prefix: data.search}
        else:
            return {"search": data.search}

    def prepare_terms_data(self, data):
        if not hasattr(data, "terms"):
            return {}
        if self.prefix:
            return {self.prefix: data.terms}
        else:
            return {"terms": data.terms}

    def prepare_times_data(self, data):
        if not hasattr(data, "times"):
            return {}
        if self.prefix:
            return {self.prefix: data.times}
        else:
            return {"times": data.times}

    def prepare_discrete_data(self, data):
        """
        Manages the exposure of exclusive search terms and prefixes.
        Exclusive terms use __and__, so send an empty dict if
        __and__ and __or__ would return the same result.
        :param data: the view data
        :return: a list of exclusive terms
        """
        if not hasattr(data, "discrete") or not isinstance(data.discrete, list):
            return {}
        if self.prefix:
            return {self.prefix: data.discrete} if len(data.discrete) > 1 else {}
        else:
            return {"discrete": data.discrete} if len(data.discrete) > 1 else {}

    class Meta:
        attrs = {"class": "table table-striped", "width": "100%"}
        template_name = "tables.html"
        terms = {}
        per_page_field = "length"
