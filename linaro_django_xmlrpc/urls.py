# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from django.urls import re_path

from linaro_django_xmlrpc.views import (
    create_token,
    delete_token,
    delete_unused_tokens,
    edit_token,
    tokens,
)

urlpatterns = [
    re_path(r"^tokens/$", tokens, name="linaro_django_xmlrpc_tokens"),
    re_path(
        r"^tokens/create/$",
        create_token,
        name="linaro_django_xmlrpc.views.create_token",
    ),
    re_path(
        r"^tokens/(?P<object_id>\d+)/delete/$",
        delete_token,
        name="linaro_django_xmlrpc.views.delete_token",
    ),
    re_path(
        r"^tokens/delete_unused/$",
        delete_unused_tokens,
        name="linaro_django_xmlrpc.views.delete_unused_tokens",
    ),
    re_path(
        r"^tokens/(?P<object_id>\d+)/edit/$",
        edit_token,
        name="linaro_django_xmlrpc.views.edit_token",
    ),
]
