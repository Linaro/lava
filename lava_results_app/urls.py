# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

"""
URL mappings for the LAVA Results application
"""
from django.conf.urls import *


urlpatterns = patterns(
    'lava_results_app.views',
    url(r'^$', 'index', name='lava.results'),
    url(r'^query$', 'query.views.query_list', name='lava.results.query_list'),
    url(r'^query/\+add$', 'query.views.query_add',
        name='lava.results.query_add'),
    url(r'^query/\+custom$',
        'query.views.query_custom', name='lava.results.query_custom'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)$',
        'query.views.query_display', name='lava.results.query_display'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+detail$',
        'query.views.query_detail', name='lava.results.query_detail'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+edit$',
        'query.views.query_edit', name='lava.results.query_edit'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+delete$',
        'query.views.query_delete', name='lava.results.query_delete'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+toggle-published$', 'query.views.query_toggle_published', name='lava.results.query_toggle_published'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+add-condition$', 'query.views.query_add_condition', name='lava.results.query_add_condition'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+remove-condition$', 'query.views.query_remove_condition', name='lava.results.query_remove_condition'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+edit-condition$', 'query.views.query_edit_condition', name='lava.results.query_edit_condition'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)$',
        'testjob', name='lava.results.testjob'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/csv$',
        'testjob_csv', name='lava.results.testjob_csv'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/yaml$',
        'testjob_yaml', name='lava.results.testjob_yaml'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)$',
        'suite', name='lava.results.suite'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/csv$',
        'suite_csv', name='lava.results.suite_csv'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/stream/csv$',
        'suite_csv_stream', name='lava.results.suite_csv_stream'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/yaml$',
        'suite_yaml', name='lava.results.suite_yaml'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/(?P<case>[-_a-zA-Z0-9.]+)$',
        'testcase', name='lava.results.testcase')
)
