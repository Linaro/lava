# Copyright (C) 2013-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

import django_tables2 as tables
from django.conf import settings

if TYPE_CHECKING:
    from typing import ClassVar

    from django.http import HttpRequest
    from django_filters import FilterSet


class LavaView(tables.SingleTableView):
    def __init__(self, request: HttpRequest, **kwargs):
        super().__init__(**kwargs)
        self.request = request
        self.filter_set: FilterSet | None = None

    def get_table_data(self, prefix: str | None = None):
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

        if (filter_set_class := self.table_class.Meta.filters) is not None:
            self.filter_set = filter_set_class(
                self.request.GET, queryset=data, request=self.request, prefix=prefix
            )
            data = self.filter_set.qs

        return data


class LavaTable(tables.Table):
    """
    Base class for all django-tables2 support in LAVA
    Provides search wrapper support for single tables
    and tables using prefixes, as well as a default page length.
    """

    def __init__(
        self,
        *args,
        request: HttpRequest = None,
        prefix: str = "",
        filter_set: FilterSet | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.request = request
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
        self.prefix = prefix
        self.filter_set = filter_set

    @classmethod
    def has_searches(cls) -> bool:
        return cls.Meta.filters is not None

    class Meta:
        attrs: ClassVar[dict[str, str]] = {
            "class": "table table-striped",
            "width": "100%",
        }
        template_name: ClassVar[str] = "tables.html"
        per_page_field: ClassVar[str] = "length"

        # LAVA table searches
        filters: type[FilterSet] | None = None
        searches: ClassVar[dict[str, str]] = {}
        queries: ClassVar[dict[str, str]] = {}
        times: ClassVar[dict[str, str]] = {}
