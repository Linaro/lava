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

import os
import versiontools

import lava_server
from lava_server.extension import Menu, loader
from django.core.urlresolvers import reverse
from django.conf import settings


def lava(request):
    try:
        instance_name = os.environ["LAVA_INSTANCE"]
    except KeyError:
        try:
            instance_name = os.path.basename(os.environ["VIRTUAL_ENV"])
        except KeyError:
            instance_name = None
            from lava_server.settings.config_file import ConfigFile
            instance_path = "/etc/lava-server/instance.conf"
            if os.path.exists(instance_path):
                instance_config = ConfigFile.load(instance_path)
                instance_name = instance_config.LAVA_INSTANCE

    return {
        'lava': {
            'extension_list': loader.extensions,
            'instance_name': instance_name,
            'branding_url': settings.BRANDING_URL,
            'branding_icon': settings.BRANDING_ICON,
            'branding_alt': settings.BRANDING_ALT,
            'branding_height': settings.BRANDING_HEIGHT,
            'branding_width': settings.BRANDING_WIDTH
        }
    }


def openid_available(request):
    openid_enabled = "django_openid_auth.auth.OpenIDBackend" in settings.AUTHENTICATION_BACKENDS
    # Check if we use generic OpenID or Launchpad.net
    openid_url = getattr(settings, "OPENID_SSO_SERVER_URL", "")
    if "ubuntu.com" in openid_url or "launchpad.net" in openid_url:
        provider = 'Launchpad.net'
    else:
        provider = "OpenID"
    return {"openid_available": openid_enabled, "openid_provider": provider}


def ldap_available(request):
    ldap_enabled = "django_auth_ldap.backend.LDAPBackend" in settings.AUTHENTICATION_BACKENDS
    login_message_ldap = getattr(settings, "LOGIN_MESSAGE_LDAP", "")
    return {"ldap_available": ldap_enabled,
            "login_message_ldap": login_message_ldap}
