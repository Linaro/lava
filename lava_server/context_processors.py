# -*- coding: utf-8 -*-
# Copyright (C) 2010-2018 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

from lava_server.settings.config_file import ConfigFile
from django.conf import settings


def lava(request):
    return {
        "lava": {
            "instance_name": settings.INSTANCE_NAME,
            "branding_url": settings.BRANDING_URL,
            "branding_icon": settings.BRANDING_ICON,
            "branding_alt": settings.BRANDING_ALT,
            "branding_height": settings.BRANDING_HEIGHT,
            "branding_width": settings.BRANDING_WIDTH,
            "branding_bug_url": settings.BRANDING_BUG_URL,
            "branding_source_url": settings.BRANDING_SOURCE_URL,
            "branding_message": settings.BRANDING_MESSAGE,
        }
    }


def ldap_available(request):
    ldap_enabled = (
        "django_auth_ldap.backend.LDAPBackend" in settings.AUTHENTICATION_BACKENDS
    )
    login_message_ldap = getattr(settings, "LOGIN_MESSAGE_LDAP", "")
    return {"ldap_available": ldap_enabled, "login_message_ldap": login_message_ldap}
