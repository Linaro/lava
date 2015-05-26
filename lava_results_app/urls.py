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
    url(r'^query$', 'query', name='lava.results.query'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)$',
        'testjob', name='lava.results.testjob'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)$',
        'suite', name='lava.results.suite'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/(?P<case>[-_a-zA-Z0-9.]+)$',
        'testcase', name='lava.results.testcase')
)
