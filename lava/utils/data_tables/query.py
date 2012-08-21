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


class DataTableQuery(object):
    """
    Query to data table server backend
    """

    DEFAULT_DISPLAY_LENGTH = 10

    def __init__(self, request):
        # Store the request object
        self.request = request

        # Number of columns
        self.iColumns = int(request.GET.get('iColumns', 0))
        self.sColumns = request.GET.get('sColumns', '')

        # Echo data (seems to be cache poison, needs follow up checks)
        self.sEcho = request.GET.get('sEcho', 0)

        # Some unspecified value
        # XXX: What is this for?
        self._ = request.GET.get('_', '')

        # Data window parameters
        self.iDisplayStart = int(request.GET.get('iDisplayStart', 0))
        self.iDisplayLength = int(request.GET.get('iDisplayLength', self.DEFAULT_DISPLAY_LENGTH))

        # Sorting/ordering parameters
        self.sorting_columns = []
        self.iSortingCols = int(request.GET.get('iSortingCols', 0))
        for i in range(self.iSortingCols):
            column_index = int(request.GET.get('iSortCol_{0}'.format(i), 0))
            sortable = request.GET.get('bSortable_{0}'.format(column_index), 'false') == 'true'
            if sortable:
                sorting_direction = request.GET.get('sSortDir_{0}'.format(i), 'asc')
                self.sorting_columns.append((column_index, sorting_direction))

        # Global search parameters
        self.sSearch = request.GET.get('sSearch', '')
        self.bRegex = request.GET.get('bRegex', 'false') == 'true'

        # Per-column search parameters
        self.search_columns = []
        for i in range(self.iColumns):
            searchable = request.GET.get('bSearchable_{0}'.format(i), 'false') == 'true'
            if searchable:
                regex = request.GET.get('bRegex_{0}'.format(i), 'false') == 'true'
                term = request.GET.get('sSearch_{0}'.format(i), '')
                self.search_columns.append((i, regex, term))
