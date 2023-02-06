# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from django.urls import path

from linaro_django_xmlrpc.views import (
    create_token,
    delete_token,
    delete_unused_tokens,
    edit_token,
    tokens,
)

urlpatterns = (
    path("tokens/", tokens, name="linaro_django_xmlrpc_tokens"),
    path(
        "tokens/create/",
        create_token,
        name="linaro_django_xmlrpc.views.create_token",
    ),
    path(
        "tokens/<int:object_id>/delete/",
        delete_token,
        name="linaro_django_xmlrpc.views.delete_token",
    ),
    path(
        "tokens/delete_unused/",
        delete_unused_tokens,
        name="linaro_django_xmlrpc.views.delete_unused_tokens",
    ),
    path(
        "tokens/<int:object_id>/edit/",
        edit_token,
        name="linaro_django_xmlrpc.views.edit_token",
    ),
)
