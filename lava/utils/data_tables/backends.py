# Copyright (C) 2012 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
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


def _identity(obj):
    return obj


class Column(object):
    """
    Column definition for the QuerySetBackend
    """

    def __init__(self, name, filter_expr, callback=None):
        self.name = name
        self.filter_expr = filter_expr
        self.callback = callback or _identity


class QuerySetBackend(_BackendBase):
    """
    Database backend for data tables.

    Stores and processes/computes the data in the database. Needs a queryset
    object and a mapping between colums and query values.
    """

    def __init__(self, queryset=None, queryset_cb=None, columns=None):
        self.queryset = queryset
        self.queryset_cb = queryset_cb
        self.columns = columns
        if not queryset and not queryset_cb:
            raise ImproperlyConfigured(
                "QuerySetBackend requires either queryset or queryset_cb")
        if not columns:
            raise ImproperlyConfigured(
                "QuerySetBackend requires columns")

    def process(self, query):
        # Get the basic response structure
        response = super(QuerySetBackend, self).process(query)
        # Get a queryset object
        if self.queryset:
            queryset = self.queryset
        else:
            queryset = self.queryset_cb(query.request)
        # 1) Apply search/filtering
        if query.sSearch:
            if query.bRegex:
                raise NotImplementedError("Searching with regular expresions is not implemented")
            else:
                raise NotImplementedError("Searching is not implemented")
                #for column in 
                #kwargz = {searchableColumn+"__icontains" : customSearch}
                #outputQ = outputQ | Q(**kwargz) if outputQ else Q(**kwargz)             
                #queryset = queryset.filter(
                #data = [row for row in data if any((query.sSearch in unicode(cell) for cell in row))]
        # TODO: Support per-column search
        # Remember how many records matched filtering
        response['iTotalDisplayRecords'] = queryset.count()
        # 2) Apply sorting
        order_by = [
            "{asc_desc}{column}".format(
                asc_desc="-" if order == 'desc' else '',
                column=self.columns[column_index].filter_expr)
            for column_index, order in query.sorting_columns]
        queryset = queryset.order_by(*order_by)
        # 3) Apply offset/limit
        queryset = queryset[query.iDisplayStart:query.iDisplayStart + query.iDisplayLength]
        #  Compute the response
        # Note, despite the 'aaData'' identifier we're
        # returing aoData-typed result (array of objects)
        # print queryset.values(*[column.filter_expr for column in self.columns])
        print queryset.values(*[column.filter_expr for column in self.columns])
        response['aaData'] = [
            dict([(column.name, unicode(column.callback(object)))
                  for column in self.columns])
            for object in queryset]
        return response
