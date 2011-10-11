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

from django.http import HttpResponse
from django.template import loader, RequestContext
from django.views.generic.simple import direct_to_template

from lava_server.extension import loader as extension_loader


def index(request):
    # Start with a list of extensions
    data = {'extension_list': extension_loader.extensions}
    # Append each extension context data
    for extension in extension_loader.extensions:
        data.update(extension.get_front_page_context())
    # Load and render the template
    context = RequestContext(request, data)
    template = loader.get_template('index.html')
    return HttpResponse(template.render(context))


def version(request):
    return direct_to_template(request, 'version_details.html')
