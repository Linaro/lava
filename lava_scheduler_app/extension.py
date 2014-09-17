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
            Menu("Devices", reverse("lava.scheduler.active_devices")),
            Menu("Queue", reverse("lava.scheduler.queue")),
            Menu("Reports", reverse("lava.scheduler.reports")),
            Menu("Submit Job", reverse("lava.scheduler.job.submit")),
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

    def contribute_to_settings(self, settings_module):
        super(SchedulerExtension, self).contribute_to_settings(settings_module)
        if 'django_tables2' not in settings_module['INSTALLED_APPS']:
            settings_module['INSTALLED_APPS'].append('django_tables2')
        from_module = settings_module.get('SCHEDULER_DAEMON_OPTIONS', {})
        settings_module['SCHEDULER_DAEMON_OPTIONS'] = {
            'LOG_FILE_PATH': None,
            'LOG_LEVEL': "WARNING",
            # 500 megs should be enough for anyone
            'LOG_FILE_SIZE_LIMIT': 500 * 1024 * 1024,
            # Jobs always specify a timeout, but I suspect its often too low.
            # So we don't let it go below this value, which defaults to a day.
            'MIN_JOB_TIMEOUT': 24 * 60 * 60,
        }
        settings_module['SCHEDULER_DAEMON_OPTIONS'].update(from_module)
        prepend_label_apps = settings_module.get('STATICFILES_PREPEND_LABEL_APPS', [])
        if self.app_name in prepend_label_apps:
            prepend_label_apps.remove(self.app_name)

    def contribute_to_settings_ex(self, settings_module, settings_object):
        super(SchedulerExtension, self).contribute_to_settings_ex(
            settings_module, settings_object)
        settings_module['SCHEDULER_DAEMON_OPTIONS'].update(
            settings_object.get_setting('SCHEDULER_DAEMON_OPTIONS', {}))
