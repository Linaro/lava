# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of linaro-django-xmlrpc.
#
# linaro-django-xmlrpc is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# linaro-django-xmlrpc is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with linaro-django-xmlrpc.  If not, see <http://www.gnu.org/licenses/>.


from django.conf.urls import url

from linaro_django_xmlrpc.views import (
    create_token,
    delete_token,
    delete_unused_tokens,
    edit_token,
    tokens,
)


urlpatterns = [
    url(r"^tokens/$", tokens, name="linaro_django_xmlrpc_tokens"),
    url(
        r"^tokens/create/$",
        create_token,
        name="linaro_django_xmlrpc.views.create_token",
    ),
    url(
        r"^tokens/(?P<object_id>\d+)/delete/$",
        delete_token,
        name="linaro_django_xmlrpc.views.delete_token",
    ),
    url(
        r"^tokens/delete_unused/$",
        delete_unused_tokens,
        name="linaro_django_xmlrpc.views.delete_unused_tokens",
    ),
    url(
        r"^tokens/(?P<object_id>\d+)/edit/$",
        edit_token,
        name="linaro_django_xmlrpc.views.edit_token",
    ),
]
