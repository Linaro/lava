# Copyright (C) 2012 Linaro Limited
#
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

"""Tables designed to be used with the DataTables jQuery plug in.

There are just three steps to using this:

1) Define the table::

    class BookTable(DataTablesTable):
        author = Column()
        title = Column()
        def get_queryset(self):
            return Book.objects.all()

2) Define a view for providing the data from the table in json format::

    def book_table_json(request):
        return BookTable.json(request)

3) Include the table in the view for the page you are building::

    def book_list(request):
        return render_to_response(
            'my_bookshop_app/book_list.html',
            {
                'book_table': BookTable('booklist', reverse(book_table_json))
            },
            RequestContext(request))

   and in the template::

    <script type="text/javascript" src=".../jquery.min.js">
    </script>
    <script type="text/javascript" src=".../jquery.dataTables.min.js">
    </script>
    {% load django_tables2 %}

    ...

    {% render_table book_table %}

That's it!

If the table depends on some parameter, you can pass paramters which end up
getting passed to the get_queryset method.  For example::

    class AuthorBookTable(DataTablesTable):
        title = Column()
        def get_queryset(self, author):
            return author.books

    def author_book_table_json(request, name):
        author = get_object_or_404(Author, name=name)
        return AuthorBookTable.json(request, (author,))

    def author_book_list(request, name):
        return render_to_response(
            author = get_object_or_404(Author, name=name)
            'my_bookshop_app/author_book_list.html',
            {
                'author': author,
                'author_book_table': AuthorBookTable(
                    'booklist', reverse(author_book_table_json))
            },
            RequestContext(request))

In general, usage is designed to be very similar to using the raw
django-tables2 tables.  Because the data in the table rendered into html and
in the json view need to be consistent, many of the options that you can pass
to Table's __init__ are not available for DataTablesTable.  In practice this
means that you need a DataTablesTable subclass for each different table.
"""

import simplejson

from django.template import RequestContext

from django_tables2.tables import Table
from django_tables2.utils import AttributeDict

from lava.utils.data_tables.views import DataTableView
from lava.utils.data_tables.backends import TableBackend


class DataTablesTable(Table):
    """A table designed to be used with the DataTables jQuery plug in.
    """

    def __init__(self, id, data=None, source=None, params=(), sortable=None,
                 empty_text=None, attrs=None, template=None):
        """Initialize the table.

        Options that Table supports that affect the data presented are not
        supported in this subclass.  Extra paramters are:

        :param id: The id of the table in the resulting HTML.  You just need
            to provide something that will be unique in the generated page.
        :param data: XXX
        :param source: The URL to get json data from.
        :param params: A tuple of arguments to pass to the get_queryset()
            method.
        """
        if data is not None:
            if source is not None or self.source is not None:
                raise AssertionError("XXX")
            elif params is not None:
                raise AssertionError("XXX")
        else:
            data = []
            if source is not None:
                self.source = source
        if template is None:
            template = 'ajax_table.html'
        # Even if this is an ajax backed table, we pass data here and patch
        # the queryset in below because of a bootstrapping issue: we want to
        # sort the initial queryset, and this is much cleaner if the table has
        # has its .columns set up which is only done in Table.__init__...
        super(DataTablesTable, self).__init__(
            data=data, sortable=sortable, empty_text=empty_text, attrs=attrs,
            template=template)
        if self.source is not None:
            self.full_queryset = self.get_queryset(*params)
            self.full_length = self.full_queryset.count()
            ordering = self.datatable_opts.get('aaSorting', [[0, 'asc']])
            sorted_queryset = TableBackend(self).apply_sorting_columns(
                self.full_queryset, ordering)
            display_length = self.datatable_opts.get('iDisplayLength', 10)
            del self.data.list
            self.data.queryset = sorted_queryset[:display_length]
        # We are careful about modifying the attrs here -- if it comes from
        # class Meta:-type options, we don't want to modify the original
        # value!
        if self.attrs:
            attrs = AttributeDict(self.attrs)
        else:
            attrs = AttributeDict()
        attrs.update({
            'id': id,
            # Forcing class to display here is a bit specific really.
            'class': 'display',
            })
        self.attrs = attrs

    @classmethod
    def json(cls, request, params=()):
        """Format table data according to request.

        This method is designed to be called from the view that is passed as
        the 'source' argument to a table.  The simplest implementation of such
        a view would be something like::

            def table_data(request):
                return MyTable.json(request)

        but in general the view might take paramters and pass them as the
        `params` argument to this function.

        :param params: A tuple of arguments to pass to the table's
            get_queryset() method.
        """
        table = cls(None, params=params)
        table.context = RequestContext(request)
        return DataTableView.as_view(
            backend=TableBackend(table)
            )(request)

    def datatable_options(self):
        """The DataTable options for this table, serialized as JSON."""
        opts = {
            'bJQueryUI': True,
            'bProcessing': True,
            'bFilter': True,
            }
        opts.update(self.datatable_opts)
        if self.source is not None:
            opts.update({
                'bServerSide': True,
                'sAjaxSource': self.source,
                'bFilter': bool(self.searchable_columns),
                'iDeferLoading': self.full_length,
                })
        aoColumnDefs = opts['aoColumnDefs'] = []
        for col in self.columns:
            aoColumnDefs.append({
                'bSortable': bool(col.sortable),
                'mDataProp': col.name,
                'aTargets': [col.name],
                })
        return simplejson.dumps(opts)

    # Any subclass might want to provide values for datatable_opts.

    # Extra DataTable options.  Values you might want to override here include
    # 'iDisplayLength' (how big to make the table's pages by default) and
    # 'aaSorting' (the initial sort of the table).  See
    # http://datatables.net/usage/options for more.
    datatable_opts = {}

    # Subclasses that use dynamic data *must* override get_queryset() and may
    # want to provide values for source, and searchable_columns.

    def get_queryset(self, *args):
        """The data the table displays.

        The return data will be sorted, filtered and sliced depending on how
        the table is manipulated by the user.
        """
        raise NotImplementedError(self.get_queryset)

    # The URL to get data from (i.e. the sAjaxSource of the table).  Often
    # it's more convenient to pass this to the table __init__ to allow the
    # code to be laid out in a more logical order.
    source = None

    # Perform searches by looking in these columns.  Searching will not be
    # enabled unless you set this.  Searching is only supported in textual
    # columns for now (supporting an IntegerField with Choices seems possible
    # too).
    searchable_columns = []
