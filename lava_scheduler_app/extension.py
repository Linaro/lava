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

from lava_server.extension import LavaServerExtension, Menu


class SchedulerExtension(LavaServerExtension):
    """
    Demo extension that shows how to integrate third party
    components into LAVA server.
    """

    @property
    def app_name(self):
        return "lava_scheduler_app"

    @property
    def api_class(self):
        from lava_scheduler_app.api import SchedulerAPI
        return SchedulerAPI

    @property
    def name(self):
        return "Scheduler"

    @property
    def main_view_name(self):
        return "lava_scheduler_app.views.index"

    def get_menu(self):
        from django.core.urlresolvers import reverse
        menu = super(SchedulerExtension, self).get_menu()
        menu.sub_menu = [
            Menu("Status", reverse("lava.scheduler")),
            Menu("Jobs", reverse("lava.scheduler.job.list")),
        ]
        return menu

    @property
    def description(self):
        return "Scheduler application for LAVA server"

    @property
    def version(self):
        import versiontools
        import lava_scheduler_app
        return versiontools.format_version(
            lava_scheduler_app.__version__, lava_scheduler_app)
