# Copyright (C) 2013-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import django_tables2 as tables
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

if TYPE_CHECKING:
    from typing import ClassVar


class LavaView(tables.SingleTableView):
    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request

    def get_table_data(self, prefix: str = ""):
        """Create queryset and add filters based on HTTP query of the request.

        4 types of filters:

        1). Simple text field search. Field must contain value.
        2). Custom query filter. Query function will be called with passed value.
        3). General search. Searches all simple text fields and all queries.
        4). Time filter. Difference between now and field value cannot be larger
            than value.

        :return: filtered queryset
        """
        data = self.get_queryset()
        if not self.table_class or not hasattr(self.table_class, "Meta"):
            return data

        q = Q()
        # Simple text field search
        for field_name in self.table_class.Meta.searches.keys():
            searched_value = self.request.GET.get(f"{prefix}{field_name}")
            if searched_value:
                q &= Q(**{f"{field_name}__contains": searched_value})

        # Query
        for func_attr_name, http_query_key in self.table_class.Meta.queries.items():
            queried_value = self.request.GET.get(f"{prefix}{http_query_key}")
            if queried_value:
                q &= getattr(self, func_attr_name)(queried_value)

        # general OR searches
        general_search = self.request.GET.get(f"{prefix}search")

        if general_search:
            # Search by searchable fields
            for field_name, field_operator in self.table_class.Meta.searches.items():
                q |= Q(**{f"{field_name}__{field_operator}": general_search})

            # Search inside queryable queries
            for func_attr_name in self.table_class.Meta.queries.keys():
                q |= getattr(self, func_attr_name)(general_search)

        # Time filter
        for field_name, time_unit in self.table_class.Meta.times.items():
            time_search = self.request.GET.get(field_name)
            if time_search:
                q &= Q(
                    **{
                        f"{field_name}__gte": timezone.now()
                        - timedelta(**{time_unit: int(time_search)})
                    }
                )

        return data.filter(q)


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
        attrs: ClassVar[dict[str, str]] = {
            "class": "table table-striped",
            "width": "100%",
        }
        template_name: ClassVar[str] = "tables.html"
        per_page_field: ClassVar[str] = "length"

        # LAVA table searches
        searches: ClassVar[dict[str, str]] = {}
        queries: ClassVar[dict[str, str]] = {}
        times: ClassVar[dict[str, str]] = {}
