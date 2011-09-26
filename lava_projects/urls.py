# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

from django.conf.urls.defaults import *


urlpatterns = patterns(
    'lava_projects.views',
    url('^$', 'project_root', name='lava.project.root'),
    url(r'^\+list/$', 'project_list', name='lava.project.list'),
    url(r'^\+register/$', 'project_register', name='lava.project.register'),
    url(r'^(?P<identifier>[a-z0-9-]+)/$', 'project_detail', name='lava.project.detail'),
    url(r'^(?P<identifier>[a-z0-9-]+)/\+update/$', 'project_update', name='lava.project.update'),
    url(r'^(?P<identifier>[a-z0-9-]+)/\+rename/$', 'project_rename', name='lava.project.rename'),
)
