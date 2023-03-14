# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from lava_server.compat import url
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
