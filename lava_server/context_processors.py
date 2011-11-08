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

import versiontools

import lava_server
from lava_server.extension import Menu, loader
from django.core.urlresolvers import reverse


def lava(request):
    menu_list = [
        Menu("LAVA", reverse('lava.home')),
    ]
    for extension in loader.extensions:
        menu = extension.get_menu()
        if menu:
            menu_list.append(menu)
    menu_list.extend([
        Menu("Documentation", "http://lava.rtfd.org/"),
        Menu("API", reverse("lava.api_help"), [
            Menu("Available Methods", reverse("lava.api_help")),
            Menu("Authentication Tokens", reverse("linaro_django_xmlrpc.views.tokens")),
        ])
    ])
    return {
        'lava': {
            'menu_list': menu_list, 
            'extension_list': loader.extensions,
            'version': versiontools.format_version(
                lava_server.__version__, hint=lava_server)}}
