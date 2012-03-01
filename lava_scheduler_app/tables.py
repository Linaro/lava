import simplejson

import django_tables2 as tables
from django_tables2.utils import AttributeDict

from lava.utils.data_tables.views import DataTableView
from lava.utils.data_tables.backends import QuerySetBackend


class AjaxColumn(tables.Column):
    def __init__(self, *args, **kw):
        render = kw.pop('render', None)
        format = kw.pop('format', unicode)
        sort_expr = kw.pop('sort_expr', None)
        width = kw.pop('width', None)
        super(AjaxColumn, self).__init__(*args, **kw)
        self.render = render
        self.format = format
        self.sort_expr = sort_expr
        self.width = width


class _ColWrapper(object):
    def __init__(self, name, column):
        self.name = name
        self.column = column

    @property
    def sort_expr(self):
        if self.column.sort_expr:
            return self.column.sort_expr
        else:
            return self.name

    def callback(self, x):
        if self.column.render:
            return self.column.render(x)
        else:
            format = self.column.format
            return format(getattr(x, self.name))


class AjaxTable(tables.Table):
    datatable_opts = None

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
        our_cols = [_ColWrapper(name, col) for name, col in cls.base_columns.iteritems()]
        return DataTableView.as_view(
            backend=QuerySetBackend(
                queryset=queryset,
                columns=our_cols)
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
            })
        aoColumnDefs = opts['aoColumnDefs'] = []
        for col in self.columns:
            aoColumnDefs.append({
                'bSortable': col.sortable,
                'mDataProp': col.name,
                'aTargets': [col.name],
                })
            if col.column.width:
                aoColumnDefs[-1]['sWidth'] = col.column.width
        return simplejson.dumps(opts)
