import simplejson

from django.template import RequestContext

from django_tables2.tables import Table
from django_tables2.utils import AttributeDict

from lava.utils.data_tables.views import DataTableView
from lava.utils.data_tables.backends import (
    TableBackend,
    )


class AjaxTable(Table):

    def __init__(self, id, source=None, params=(), **kw):
        if 'template' not in kw:
            kw['template'] = 'lava_scheduler_app/ajax_table.html'
        super(AjaxTable, self).__init__(data=[], **kw)
        self.full_queryset = self.get_queryset(*params)
        self.full_length = self.full_queryset.count()
        ordering = self.datatable_opts.get('aaSorting', [[0, 'asc']])
        sorted_queryset = TableBackend(self).apply_sorting_columns(
            self.full_queryset, ordering)
        display_length = self.datatable_opts.get('iDisplayLength', 10)
        del self.data.list
        self.data.queryset = sorted_queryset[:display_length]
        if source is not None:
            self.source = source
        # Overriding the attrs like this is a bit specific really
        self.attrs = AttributeDict({
            'id': id,
            'class': 'display',
            })

    @classmethod
    def json(cls, request, params=()):
        table = cls(None, params=params)
        table.context = RequestContext(request)
        return DataTableView.as_view(
            backend=TableBackend(table)
            )(request)

    def datatable_options(self):
        opts = {
            'bJQueryUI': True,
            'bServerSide': True,
            'bProcessing': True,
            'sAjaxSource': self.source,
            'bFilter': bool(self.searchable_columns),
            'iDeferLoading': self.full_length,
            }
        opts.update(self.datatable_opts)
        aoColumnDefs = opts['aoColumnDefs'] = []
        for col in self.columns:
            aoColumnDefs.append({
                'bSortable': bool(col.sortable),
                'mDataProp': col.name,
                'aTargets': [col.name],
                })
        return simplejson.dumps(opts)

    source = None
    datatable_opts = {}
    searchable_columns = []

    def get_queryset(self, *args):
        raise NotImplementedError

