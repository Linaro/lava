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


from optparse import make_option

from lava_scheduler_app.management.commands import SchedulerCommand


class Command(SchedulerCommand):

    help = "Run the LAVA test job scheduler"
    option_list = SchedulerCommand.option_list + (
        make_option('--use-fake',
                    action='store_true',
                    dest='use_fake',
                    default=False,
                    help="Use fake dispatcher (for testing)"),
        make_option('--dispatcher',
                    action="store",
                    dest="dispatcher",
                    default="lava-dispatch",
                    help="Dispatcher command to invoke"),
    )

    def handle(self, *args, **options):
        import os

        from twisted.internet import reactor

        from lava_scheduler_daemon.service import JobQueue
        from lava_scheduler_daemon.worker import WorkerData
        from lava_scheduler_daemon.dbjobsource import DatabaseJobSource
        import xmlrpclib

        daemon_options = self._configure(options)

        source = DatabaseJobSource()

        if options['use_fake']:
            import lava_scheduler_app
            opd = os.path.dirname
            dispatcher = os.path.join(
                opd(opd(os.path.abspath(lava_scheduler_app.__file__))),
                'fake-dispatcher')
        else:
            dispatcher = options['dispatcher']

        # Update complete worker heartbeat data. This will be run once,
        # on every start/restart of the scheduler daemon.
        worker = WorkerData()
        try:
            worker.put_heartbeat_data(restart=True)
        except (xmlrpclib.Fault, xmlrpclib.ProtocolError) as err:
            worker.logger.error("Complete heartbeat update failed!")

        # Start scheduler service.
        service = JobQueue(
            source, dispatcher, reactor, daemon_options=daemon_options)
        reactor.callWhenRunning(service.startService)
        reactor.run()
