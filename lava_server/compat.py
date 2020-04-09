# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from django.utils.version import get_version
from django.core.management.base import CommandParser
from rest_framework_extensions import __version__ as DRFE_VERSION_STR
import rest_framework_filters as filters


DJANGO_VERSION = get_version()
DRFE_VERSION = [int(n) for n in DRFE_VERSION_STR.split(".")]


# Handles compatibility for django_restframework_filters
try:
    from rest_framework_filters.backends import RestFrameworkFilterBackend  # noqa

    # RelatedFilter argument "name" as been renamed "field_name"
    def RelatedFilter(cls, name, queryset):
        return filters.RelatedFilter(cls, field_name=name, queryset=queryset)


except ImportError:
    from rest_framework_filters.backends import (
        DjangoFilterBackend as RestFrameworkFilterBackend,
    )  # noqa

    # Keep the original version
    def RelatedFilter(cls, name, queryset):
        return filters.RelatedFilter(cls, name=name, queryset=queryset)


FilterBackend = RestFrameworkFilterBackend


class NoMarkupFilterBackend(FilterBackend):
    def to_html(self, request, queryset, view):
        # In order to prevent a huge performance issue when rendering the
        # browsable API, do not render the choice fields.
        return ""


def add_permissions(default_in_django2, local):
    if DJANGO_VERSION >= "2":
        return local
    else:
        return default_in_django2 + local


def get_sub_parser_class(cmd):
    class SubParser(CommandParser):
        """
        Sub-parsers constructor that mimic Django constructor.
        See http://stackoverflow.com/a/37414551
        """

        def __init__(self, **kwargs):
            if DJANGO_VERSION >= "2":
                kwargs.update(
                    {
                        "called_from_command_line": getattr(
                            cmd, "_called_from_command_line", None
                        )
                    }
                )
                super().__init__(**kwargs)
            else:
                super().__init__(cmd, **kwargs)

    return SubParser


def drf_basename(name):
    """
    Handles compatibility with different versions of djangorestframework, in
    terms of the deprecation of `base_name` when registering ViewSets on DRF >=
    3.10.
    """
    if DRFE_VERSION >= [0, 6]:
        return {"basename": name}
    else:
        return {"base_name": name}


try:
    from django_tables2.paginators import LazyPaginator

    def djt2_paginator_class():
        return {"paginator_class": LazyPaginator}


except ImportError:
    from django.core.paginator import EmptyPage, Page, PageNotAnInteger, Paginator
    from django.utils.translation import gettext as _

    class LazyPaginator(Paginator):
        """
        Implement lazy pagination, preventing any count() queries.

        By default, for any valid page, the total number of pages for the paginator will be

         - `current + 1` if the number of records fetched for the current page offset is
           bigger than the number of records per page.
         - `current` if the number of records fetched is less than the number of records per page.

        The number of additional records fetched can be adjusted using `look_ahead`, which
        defaults to 1 page. If you like to provide a little more extra information on how much
        pages follow the current page, you can use a higher value.

        .. note::

            The number of records fetched for each page is `per_page * look_ahead + 1`, so increasing
            the value for `look_ahead` makes the view a bit more expensive.

        So::

            paginator = LazyPaginator(range(10000), 10)

            >>> paginator.page(1).object_list
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
            >>> paginator.num_pages
            2
            >>> paginator.page(10).object_list
            [91, 92, 93, 94, 95, 96, 97, 98, 99, 100]
            >>> paginator.num_pages
            11
            >>> paginator.page(1000).object_list
            [9991, 9992, 9993, 9994, 9995, 9996, 9997, 9998, 9999]
            >>> paginator.num_pages
            1000

        Usage with `~.SingleTableView`::

            class UserListView(SingleTableView):
                table_class = UserTable
                table_data = User.objects.all()
                pagination_class = LazyPaginator

        Or with `~.RequestConfig`::

            RequestConfig(paginate={"paginator_class": LazyPaginator}).configure(table)

        .. versionadded :: 2.0.0
        """

        look_ahead = 1

        def __init__(self, object_list, per_page, look_ahead=None, **kwargs):
            self._num_pages = None
            if look_ahead is not None:
                self.look_ahead = look_ahead

            super().__init__(object_list, per_page, **kwargs)

        def validate_number(self, number):
            """Validate the given 1-based page number."""
            try:
                if isinstance(number, float) and not number.is_integer():
                    raise ValueError
                number = int(number)
            except (TypeError, ValueError):
                raise PageNotAnInteger(_("That page number is not an integer"))
            if number < 1:
                raise EmptyPage(_("That page number is less than 1"))
            return number

        def page(self, number):
            number = self.validate_number(number)
            bottom = (number - 1) * self.per_page
            top = bottom + self.per_page
            # Retrieve more objects to check if there is a next page.
            look_ahead_items = (self.look_ahead - 1) * self.per_page + 1
            objects = list(
                self.object_list[bottom : top + self.orphans + look_ahead_items]
            )
            objects_count = len(objects)
            if objects_count > (self.per_page + self.orphans):
                # If another page is found, increase the total number of pages.
                self._num_pages = number + (objects_count // self.per_page)
                # In any case,  return only objects for this page.
                objects = objects[: self.per_page]
            elif (number != 1) and (objects_count <= self.orphans):
                raise EmptyPage(_("That page contains no results"))
            else:
                # This is the last page.
                self._num_pages = number
            return Page(objects, number, self)

        def _get_count(self):
            raise NotImplementedError

        count = property(_get_count)

        def _get_num_pages(self):
            return self._num_pages

        num_pages = property(_get_num_pages)

        def _get_page_range(self):
            raise NotImplementedError

        page_range = property(_get_page_range)

    def djt2_paginator_class():
        return {"klass": LazyPaginator}
