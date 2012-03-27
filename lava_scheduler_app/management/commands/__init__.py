import logging
from optparse import make_option
import sys

from django.core.management.base import BaseCommand


NOTSET = object()


class SchedulerCommand(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('-l', '--loglevel',
                    action='store',
                    default=NOTSET,
                    help="Log level, default is taken from settings."),
        make_option('-f', '--logfile',
                    action='store',
                    default=NOTSET,
                    help="Path to log file, default is taken from settings."),
        )

    log_prefix = ''

    def _configure(self, options):
        from django.conf import settings
        daemon_options = settings.SCHEDULER_DAEMON_OPTIONS.copy()
        if options['logfile'] is not NOTSET:
            daemon_options['LOG_FILE_PATH'] = options['logfile']
        if options['loglevel'] is not NOTSET:
            daemon_options['LOG_LEVEL'] = options['loglevel']
        logger = logging.getLogger('')
        if daemon_options['LOG_FILE_PATH'] is None:
            handler = logging.StreamHandler(sys.stderr)
        else:
            handler = logging.FileHandler(daemon_options['LOG_FILE_PATH'])
        fmt = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        if self.log_prefix:
            fmt = self.log_prefix + ' ' + fmt
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, daemon_options['LOG_LEVEL'].upper()))
        return daemon_options

