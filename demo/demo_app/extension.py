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
from lava_server.extension import LavaServerExtension

import demo_app


class DemoExtension(LavaServerExtension):
    """
    Demo extension that shows how to integrate third party
    components into LAVA server.
    """

    @property
    def app_name(self):
        return "demo_app"

    @property
    def name(self):
        return "Demo"

    @property
    def api_class(self):
        from demo_app.models import DemoAPI
        return DemoAPI

    @property
    def main_view_name(self):
        return "demo_app.views.hello"

    @property
    def description(self):
        return "Demo extension for LAVA server"

    @property
    def version(self):
        return versiontools.format_version(demo_app.__version__)
