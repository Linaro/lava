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


from django.core.management.base import BaseCommand
from optparse import make_option


class Command(BaseCommand):

    help = "Run the LAVA test job scheduler"
    option_list = BaseCommand.option_list + (
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
        make_option('-l', '--loglevel',
                    action='store',
                    default='WARNING',
                    help="Log level, default is WARNING"),
        make_option('-f', '--logfile',
                    action='store',
                    default=None,
                    help="Path to log file"),
    )


    def _configure_logging(self, loglevel, logfile=None):
        import logging
        import sys
        logger = logging.getLogger('')
        if logfile is None:
            handler = logging.StreamHandler(sys.stderr)
        else:
            handler = logging.FileHandler(logfile)
        handler.setFormatter(
            logging.Formatter("[%(levelname)s] [%(name)s] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, loglevel.upper()))

    def handle(self, *args, **options):
        import os

        from twisted.internet import reactor

        from lava_scheduler_daemon.service import BoardSet

        from lava_scheduler_daemon.dbjobsource import DatabaseJobSource

        self._configure_logging(options['loglevel'], options['logfile'])

        source = DatabaseJobSource()

        if options['use_fake']:
            dispatcher = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'fake-dispatcher')
        else:
            dispatcher = options['dispatcher']
        service = BoardSet(source, dispatcher, reactor)
        reactor.callWhenRunning(service.startService)
        reactor.run()
