import simplejson

import django_tables2 as tables
from django_tables2.rows import BoundRow
from django_tables2.utils import AttributeDict

from lava.utils.data_tables.views import DataTableView
from lava.utils.data_tables.backends import QuerySetBackend


class AjaxColumn(tables.Column):

    def __init__(self, *args, **kw):
        sort_expr = kw.pop('sort_expr', None)
        width = kw.pop('width', None)
        super(AjaxColumn, self).__init__(*args, **kw)
        self.sort_expr = sort_expr
        self.width = width


class _ColWrapper(object):

    def __init__(self, name, sort_expr, table):
        self.name = name
        if sort_expr is not None:
            self.sort_expr = sort_expr
        else:
            self.sort_expr = name
        self.table = table

    def callback(self, record):
        # It _might_ make life more convenient to handle certain non-JSONable
        # datatypes here -- particularly, applying unicode() to model objects
        # would be more consistent with the way templates work.
        return BoundRow(self.table, record)[self.name]


class AjaxTable(tables.Table):
    datatable_opts = None
    searchable_columns = []

    def __init__(self, id, source, **kw):
        if 'template' not in kw:
            kw['template'] = 'lava_scheduler_app/ajax_table.html'
        super(AjaxTable, self).__init__(data=[], **kw)
        self.source = source
        self.attrs = AttributeDict({
            'id': id,
            'class': 'display',
            })

    @classmethod
    def json(cls, request, queryset):
        table = cls(None, None)
        our_cols = [_ColWrapper(name, col.sort_expr, table)
                    for name, col in cls.base_columns.iteritems()]
        return DataTableView.as_view(
            backend=QuerySetBackend(
                queryset=queryset,
                columns=our_cols,
                searching_columns=cls.searchable_columns)
            )(request)

    def datatable_options(self):
        if self.datatable_opts:
            opts = self.datatable_opts.copy()
        else:
            opts = {}
        opts.update({
            'bJQueryUI': True,
            'bServerSide': True,
            'bProcessing': True,
            'sAjaxSource': self.source,
            'bFilter': bool(self.searchable_columns)
            })
        aoColumnDefs = opts['aoColumnDefs'] = []
        for col in self.columns:
            aoColumnDefs.append({
                'bSortable': bool(col.sortable),
                'mDataProp': col.name,
                'aTargets': [col.name],
                })
            if col.column.width:
                aoColumnDefs[-1]['sWidth'] = col.column.width
        return simplejson.dumps(opts)
