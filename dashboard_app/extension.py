# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

from lava_server.extension import LavaServerExtension


class DashboardExtension(LavaServerExtension):

    @property
    def app_name(self):
        return "dashboard_app"

    @property
    def name(self):
        return "Dashboard"

    @property
    def main_view_name(self):
        return "dashboard_app.views.bundle_stream_list"

    @property
    def description(self):
        return "Validation Dashboard"

    @property
    def version(self):
        from dashboard_app import __version__
        import versiontools
        return versiontools.format_version(__version__)

    @property
    def api_class(self):
        from dashboard_app.xmlrpc import DashboardAPI
        return DashboardAPI

    def contribute_to_settings(self, settings):
        super(DashboardExtension, self).contribute_to_settings(settings)
        settings['INSTALLED_APPS'].extend([
            "linaro_django_pagination",
            "south",
        ])
        settings['MIDDLEWARE_CLASSES'].append(
            'linaro_django_pagination.middleware.PaginationMiddleware')
        settings['RESTRUCTUREDTEXT_FILTER_SETTINGS'] = {
            "initial_header_level": 4}

    def contribute_to_settings_ex(self, settings_module, settings_object):
        settings_module['DATAVIEW_DIRS'] = settings_object._settings.get(
            "DATAVIEW_DIRS", [])
        settings_module['DATAREPORT_DIRS'] = settings_object._settings.get(
            "DATAREPORT_DIRS", [])
