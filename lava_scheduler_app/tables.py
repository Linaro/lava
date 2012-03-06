import simplejson

from django.template import compile_string, RequestContext

from django_tables2.columns import BoundColumn
from django_tables2.rows import BoundRow
from django_tables2.tables import Table, TableData
from django_tables2.utils import AttributeDict

from lava.utils.data_tables.views import DataTableView
from lava.utils.data_tables.backends import QuerySetBackend


simple_nodelist = compile_string('{{ a }}', None)


class _ColWrapper(object):

    def __init__(self, name, sort_expr, table):
        self.name = name
        self.sort_expr = table.columns[name].accessor.replace('.', '__')
        self.table = table

    def callback(self, record):
        context = self.table.context
        context.update({"a": BoundRow(self.table, record)[self.name]})
        try:
            return simple_nodelist.render(context)
        finally:
            context.pop()


class _AjaxTableData(TableData):
    def order_by(self, order_by):
        if order_by:
            raise AssertionError(
                "AjaxTables do not support ordering by Table options")
        return


class AjaxTable(Table):
    TableDataClass = _AjaxTableData

    def __init__(self, id, source, params=(), _for_rendering=True, **kw):
        if 'template' not in kw:
            kw['template'] = 'lava_scheduler_app/ajax_table.html'
        self.params = params
        self.total_length = None
        if _for_rendering:
            qs = self.get_queryset()
            self.total_length = qs.count()

            ordering = self.datatable_opts.get('aaSorting', [[0, 'asc']])
            # What follows is duplicated from backends.py which isn't ideal.
            order_by = []
            for column_index, order in ordering:
                name, col = self.base_columns.items()[column_index]
                sort_expr = BoundColumn(self, col, name).accessor.replace('.', '__')
                order_by.append(
                    "{asc_desc}{column}".format(
                        asc_desc="-" if order == 'desc' else '',
                        column=sort_expr))
            qs = qs.order_by(*order_by)

            display_length = self.datatable_opts.get('iDisplayLength', 10)
            qs = qs[:display_length]
        else:
            qs = []
        super(AjaxTable, self).__init__(data=qs, **kw)
        self.source = source
        self.attrs = AttributeDict({
            'id': id,
            'class': 'display',
            })

    @classmethod
    def json(cls, request, params=()):
        table = cls(None, None, params, _for_rendering=False)
        table.context = RequestContext(request)
        our_cols = [_ColWrapper(name, col.sort_expr, table)
                    for name, col in cls.base_columns.iteritems()]
        return DataTableView.as_view(
            backend=QuerySetBackend(
                queryset=table.get_queryset(),
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
        if self.total_length is not None:
            opts['iDeferLoading'] = self.total_length
        aoColumnDefs = opts['aoColumnDefs'] = []
        for col in self.columns:
            aoColumnDefs.append({
                'bSortable': bool(col.sortable),
                'mDataProp': col.name,
                'aTargets': [col.name],
                })
        return simplejson.dumps(opts)

    datatable_opts = {}
    searchable_columns = []

    def get_queryset(self):
        raise NotImplementedError

