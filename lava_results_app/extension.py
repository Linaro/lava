# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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


class ResultsExtension(LavaServerExtension):
    """
    Results extension for the Pipeline result handling.
    """

    @property
    def app_name(self):
        return "lava_results_app"

    @property
    def name(self):
        return "Results"

    @property
    def version(self):
        return ""

    @property
    def main_view_name(self):
        return "lava_results_app.views.index"

    def get_menu(self):
        from django.core.urlresolvers import reverse
        menu = super(ResultsExtension, self).get_menu()
        menu.sub_menu = [
            Menu("Results", reverse("lava.results")),
            Menu("Queries", reverse("lava.results.query_list"))
        ]
        return menu

    @property
    def description(self):
        return "Results application for LAVA server"

    def contribute_to_settings(self, settings_module):
        super(ResultsExtension, self).contribute_to_settings(settings_module)
        if 'django_tables2' not in settings_module['INSTALLED_APPS']:
            settings_module['INSTALLED_APPS'].append('django_tables2')
