# Copyright (C) 2022 Linaro
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.urls import reverse


class TestLogin:
    def test_show_login_page(self, db, client):
        ret = client.get(reverse("login"))
        assert ret.status_code == 200
