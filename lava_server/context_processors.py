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
    menu_list = [
        Menu("Home", reverse('lava.home')),
    ]
    for extension in loader.extensions:
        menu = extension.get_menu()
        if menu:
            menu_list.append(menu)
    menu_list.extend([
        Menu("API", reverse("lava.api_help"), [
            Menu("Available Methods", reverse("lava.api_help")),
            Menu("Authentication Tokens", reverse("linaro_django_xmlrpc.views.tokens")),
        ]),
        Menu("Documentation", "/static/docs/"),
    ])

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
            'menu_list': menu_list,
            'extension_list': loader.extensions,
            'instance_name': instance_name,
            'version': versiontools.format_version(
                lava_server.__version__, hint=lava_server)}}


def openid_available(request):
    openid_enabled = "django_openid_auth.auth.OpenIDBackend" in settings.AUTHENTICATION_BACKENDS
    # Check if we use generic OpenID or Launchpad.net
    openid_url = getattr(settings, "OPENID_SSO_SERVER_URL", "")
    if "ubuntu.com" in openid_url or "launchpad.net" in openid_url:
        provider = 'Launchpad.net'
    else:
        provider = "OpenID"
    return {"openid_available": openid_enabled, "openid_provider": provider}
