# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Lava Dashboard.
#
# Lava Dashboard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Dashboard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

"""
URL mappings for the Dashboard application

https://docs.djangoproject.com/en/1.8/topics/http/urls/#naming-url-patterns
https://docs.djangoproject.com/en/1.8/releases/1.8/#passing-a-dotted-path-to-reverse-and-url

Avoid letting the name attribute of a url look like a python path - use underscore
instead of period. The name is just a label, using it as a path is deprecated and
support will be removed in Django1.10. Equally, always provide a name if the URL
needs to be reversed elsewhere in the code, e.g. the view. (Best practice is to
use a name for all new urls, even if not yet used elsewhere.)
"""
from django.conf.urls import url


urlpatterns = [
]
