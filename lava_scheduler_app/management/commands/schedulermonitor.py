# Copyright (C) 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Scheduler.
#
# LAVA Scheduler is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License version 3 as
# published by the Free Software Foundation
#
# LAVA Scheduler is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Scheduler.  If not, see <http://www.gnu.org/licenses/>.

import os
import simplejson


from lava_scheduler_app.management.commands import SchedulerCommand
from lava_scheduler_daemon.dbjobsource import DatabaseJobSource


class Command(SchedulerCommand):

    help = "Run the LAVA test job scheduler"

    log_prefix = 'M'

    def handle(self, *args, **options):
        from twisted.internet import reactor
        from lava_scheduler_daemon.board import Job
        daemon_options = self._configure(options)
        source = DatabaseJobSource()
        dispatcher, board_name, json_file = args

        log_to_stdout = os.getenv("CELERY_CONFIG_MODULE", False)

        job = Job(
            simplejson.load(open(json_file)), dispatcher,
            source, board_name, reactor, daemon_options=daemon_options,
            log_to_stdout=log_to_stdout)
        def run():
            job.run().addCallback(lambda result: reactor.stop())
        reactor.callWhenRunning(run)
        reactor.run()
