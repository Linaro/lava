# Copyright (C) 2012 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.template import compile_string

from django_tables2.rows import BoundRow

from lava.utils.data_tables.interface import IBackend


class _BackendBase(IBackend):
    """
    Common code for data backends to data tables
    """

    def process(self, query):
        return {
            'sEcho': query.sEcho,
            'sColumns': query.sColumns
        }


class ArrayBackend(_BackendBase):
    """
    Array backend to data tables

    Stores all data in a plain python list. All filtering is handled in the
    running process. It is suitable for very small data sets only but has the
    advantage of being unrelated to any databases.
    """

    def __init__(self, data):
        self.data = data

    def process(self, query):
        # Get the basic response structure
        response = super(ArrayBackend, self).process(query)
        # 0) Copy original data
        # TODO: add support for lazy copy (only if really needed)
        data = list(self.data)
        response['iTotalRecords'] = len(data)
        # 1) Apply search/filtering
        if query.sSearch:
            if query.bRegex:
                raise NotImplementedError("Searching with regular expresions is not implemented")
            else:
                data = [row for row in data if any((query.sSearch in unicode(cell) for cell in row))]
        # Remember how many records matched filtering
        response['iTotalDisplayRecords'] = len(data)
        # TODO: Support regex search
        # TODO: Support per-column search
        # 2) Apply sorting
        for column_index, order in reversed(query.sorting_columns):
            data.sort(key=lambda row: row[column_index], reverse=order == 'desc')
        # 3) Apply offset/limit
        data = data[query.iDisplayStart:query.iDisplayStart + query.iDisplayLength]
        # Remember the subset of the displayed data
        response['aaData'] = data
        return response



class Column(object):
    """
    Column definition for the QuerySetBackend
    """

    def __init__(self, name, sort_expr, callback):
        self.name = name
        self.sort_expr = sort_expr
        self.callback = callback


class QuerySetBackend(_BackendBase):
    """
    Database backend for data tables.

    Stores and processes/computes the data in the database. Needs a queryset
    object and a mapping between colums and query values.
    """

    def __init__(self, queryset=None, queryset_cb=None, columns=None,
                 searching_columns=None):
        self.queryset = queryset
        self.queryset_cb = queryset_cb
        self.columns = columns
        self.searching_columns = searching_columns
        if queryset is None and queryset_cb is None:
            raise ImproperlyConfigured(
                "QuerySetBackend requires either queryset or queryset_cb")
        if not columns:
            raise ImproperlyConfigured(
                "QuerySetBackend requires columns")

    def process(self, query):
        # Get the basic response structure
        response = super(QuerySetBackend, self).process(query)
        # Get a queryset object
        if self.queryset is not None:
            queryset = self.queryset
        else:
            queryset = self.queryset_cb(query.request)
        # 1) Apply search/filtering
        if query.sSearch:
            if query.bRegex:
                raise NotImplementedError("Searching with regular expresions is not implemented")
            else:
                if self.searching_columns is None:
                    raise NotImplementedError("Searching is not implemented")
                terms = query.sSearch.split()
                andQ = None
                for term in terms:
                    orQ = None
                    for col in self.searching_columns:
                        q = Q(**{col+"__icontains" : term})
                        orQ = orQ | q if orQ else q
                    andQ = andQ & orQ if andQ else orQ
                response['iTotalRecords'] = queryset.count()
                queryset = queryset.filter(andQ)
                response['iTotalDisplayRecords'] = queryset.count()
        else:
            response['iTotalRecords'] = response['iTotalDisplayRecords'] = queryset.count()
        # TODO: Support per-column search
        # 2) Apply sorting
        order_by = [
            "{asc_desc}{column}".format(
                asc_desc="-" if order == 'desc' else '',
                column=self.columns[column_index].sort_expr)
            for column_index, order in query.sorting_columns]
        queryset = queryset.order_by(*order_by)
        # 3) Apply offset/limit
        queryset = queryset[query.iDisplayStart:query.iDisplayStart + query.iDisplayLength]
        #  Compute the response
        # Note, despite the 'aaData'' identifier we're
        # returing aoData-typed result (array of objects)
        # print queryset.values(*[column.filter_expr for column in self.columns])
        response['aaData'] = [
            dict([(column.name, column.callback(object))
                  for column in self.columns])
            for object in queryset]
        return response


simple_nodelist = compile_string('{{ value }}', None)


class TableBackend(_BackendBase):
    """
    Database backend for data tables.

    Stores and processes/computes the data in the database.
    """

    def __init__(self, table):
        self.table = table

    def _render_cell(self, col, data):
        """Render data for a column.

        The intent here is to match as precisely as possible the way a cell
        would be rendered into HTML by django-tables2.  There are two bits of
        magic in play here:

        1) calling the correct render or render_FOO method with the correct
           arguments, and
        2) the default Django rendering (escaping if needed, calling unicode()
           on model objects etc).

        The first magic is implemented in BoundRow.__getitem__, so we go
        through that, and we get the default Django rendering behaviour by
        actually rendering what __getitem__ returns in a trivially simple
        template (DataTables just sets the innerHTML of the cell to what we
        return with no escaping or what have you, so this results in
        consistent behaviour).
        """
        context = self.table.context
        context.update({"value": BoundRow(self.table, data)[col.name]})
        try:
            return simple_nodelist.render(context)
        finally:
            context.pop()

    def _build_q_for_search(self, sSearch):
        """Construct a Q object that searches for sSearch.

        The search is split into words, and we return each row that matches
        all words.

        A row matches a word if the word appears in (in the sense of
        'icontains') one of the `searchable_columns`.  This clearly only
        really works for text columns.  Extending this to work on
        IntegerFields with choices seems possible (you can translate matching
        a word into matching the values corresponding to choices whose names
        contain the word) but going significantly beyond that would require
        some hairy machinery (you could imagine auto generating a model for
        each table that stores the rendered rows and searching in that... but
        that's mad, surely).
        """
        terms = sSearch.split()
        andQ = None
        for term in terms:
            orQ = None
            for col in self.table.searchable_columns:
                q = Q(**{col+"__icontains" : term})
                orQ = orQ | q if orQ else q
            andQ = andQ & orQ if andQ else orQ
        return andQ

    def apply_sorting_columns(self, queryset, sorting_columns):
        """Sort queryset accoding to sorting_columns.

        `sorting_columns` uses the format used by DataTables, e.g. [[0,
        'asc']] or [[4, 'desc']] or even [[0, 'asc'], [1, 'desc']].
        """
        if not sorting_columns:
            return queryset
        order_by = []
        for column_index, order in sorting_columns:
            col = self.table.columns[column_index]
            order_by.append(
                "{asc_desc}{column}".format(
                    asc_desc="-" if order == 'desc' else '',
                    column=col.accessor.replace('.', '__')))
        return queryset.order_by(*order_by)

    def process(self, query):
        """Return the JSON data described by `query`."""
        # Get the basic response structure
        response = super(TableBackend, self).process(query)
        queryset = self.table.full_queryset
        response['iTotalRecords'] = self.table.full_length
        # 1) Apply search/filtering
        if query.sSearch:
            if query.bRegex:
                raise NotImplementedError(
                    "Searching with regular expresions is not implemented")
            else:
                if self.table.searchable_columns is None:
                    raise NotImplementedError("Searching is not implemented")
                queryset = queryset.filter(
                    self._build_q_for_search(query.sSearch))
                response['iTotalDisplayRecords'] = queryset.count()
        else:
            response['iTotalDisplayRecords'] = response['iTotalRecords']
        # TODO: Support per-column search
        # 2) Apply sorting
        queryset = self.apply_sorting_columns(queryset, query.sorting_columns)
        # 3) Apply offset/limit
        queryset = queryset[query.iDisplayStart:query.iDisplayStart + query.iDisplayLength]
        #  Compute the response
        # Note, despite the 'aaData' identifier we're
        # returing aoData-typed result (array of objects)
        response['aaData'] = [
            dict([(column.name, self._render_cell(column, object))
                  for column in self.table.columns])
            for object in queryset]
        return response
