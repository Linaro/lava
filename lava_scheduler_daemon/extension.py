# Copyright (C) 2014 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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

from lava_server.extension import HeadlessExtension


class SchedulerDaemonExtension(HeadlessExtension):

    @property
    def name(self):
        return "LAVA Scheduler Daemon"

    @property
    def version(self):
        import versiontools
        import lava_scheduler_app
        return versiontools.format_version(
            lava_scheduler_app.__version__, lava_scheduler_app)

    def contribute_to_settings_ex(self, settings_module, settings_object):
        settings_module['INSTALLED_APPS'].append("lava_scheduler_daemon")
