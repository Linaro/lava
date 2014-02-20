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
from django.http import HttpResponse
import simplejson
from django.views.generic import View

from lava.utils.data_tables.query import DataTableQuery


class DataTableView(View):
    """
    View for processing data table requests
    """

    backend = None

    def get(self, request, *args, **kwargs):
        if self.backend is None:
            raise ImproperlyConfigured(
                "DataTableView requires a definition of a backend")
        query = DataTableQuery(request)
        result = self.backend.process(query)
        return HttpResponse(
            simplejson.dumps(result),
            mimetype='application/json')
