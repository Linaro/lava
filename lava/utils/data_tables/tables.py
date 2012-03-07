import simplejson

from django.template import RequestContext

from django_tables2.tables import Table
from django_tables2.utils import AttributeDict

from lava.utils.data_tables.views import DataTableView
from lava.utils.data_tables.backends import (
    QuerySetBackend,
    sort_by_sorting_columns,
    )


class AjaxTable(Table):

    def __init__(self, id, source, params=(), _for_rendering=True, **kw):
        if 'template' not in kw:
            kw['template'] = 'lava_scheduler_app/ajax_table.html'
        self.params = params
        super(AjaxTable, self).__init__(data=[], **kw)
        if _for_rendering:
            qs = self.get_queryset()

            self.total_length = qs.count()

            qs = sort_by_sorting_columns(
                qs, self.columns,
                self.datatable_opts.get('aaSorting', [[0, 'asc']]))

            del self.data.list
            display_length = self.datatable_opts.get('iDisplayLength', 10)
            self.data.queryset = qs[:display_length]
        self.source = source
        # Overriding the attrs like this is a bit specific really
        self.attrs = AttributeDict({
            'id': id,
            'class': 'display',
            })

    @classmethod
    def json(cls, request, params=()):
        table = cls(None, None, params, _for_rendering=False)
        table.context = RequestContext(request)
        return DataTableView.as_view(
            backend=QuerySetBackend(
                queryset=table.get_queryset(),
                columns=table.columns.all(),
                searching_columns=cls.searchable_columns)
            )(request)

    def datatable_options(self):
        opts = {
            'bJQueryUI': True,
            'bServerSide': True,
            'bProcessing': True,
            'sAjaxSource': self.source,
            'bFilter': bool(self.searchable_columns),
            'iDeferLoading': self.total_length,
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

    datatable_opts = {}
    searchable_columns = []

    def get_queryset(self):
        raise NotImplementedError

