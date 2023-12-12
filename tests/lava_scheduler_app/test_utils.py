# Copyright (C) 2023 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_scheduler_app.utils import get_user_ip


def test_get_user_ip_forwarded_for(mocker):
    req = mocker.MagicMock()
    req.META = {"HTTP_X_FORWARDED_FOR": "88.77.66.55"}
    assert get_user_ip(req) == "88.77.66.55"


def test_get_user_ip_forwarded_for_index(mocker, settings):
    settings.HTTP_X_FORWARDED_FOR_INDEX = 1
    req = mocker.MagicMock()
    req.META = {"HTTP_X_FORWARDED_FOR": "88.77.66.55,44.33.22.11"}
    assert get_user_ip(req) == "44.33.22.11"


def test_get_user_ip_remote_addr(mocker):
    req = mocker.MagicMock()
    req.META = {"REMOTE_ADDR": "127.0.0.1"}
    assert get_user_ip(req) == "127.0.0.1"
