# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
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
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.


from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.decorators import available_attrs
from django.utils.functional import wraps

from lava_results_app.models import Query


def ownership_required(view_func):
    @wraps(view_func, assigned=available_attrs(view_func))
    def wrapper(request, *args, **kwargs):
        report_name = kwargs.get('name', None)
        query = get_object_or_404(Query, name=report_name)
        if request.user.is_superuser or query.user == request.user or \
           query.group in request.user.groups.all():
            return view_func(request, *args, **kwargs)
        else:
            raise PermissionDenied
    return wrapper
