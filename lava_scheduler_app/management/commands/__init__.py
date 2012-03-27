import logging
import sys

from django.core.management.base import BaseCommand


class SchedulerCommand(BaseCommand):

    log_prefix = ''

    def _configure(self, log_level, log_file):
        from django.conf import settings
        daemon_options = settings.SCHEDULER_DAEMON_OPTIONS.copy()
        daemon_options['LOG_FILE'] = log_file
        daemon_options['LOG_LEVEL'] = log_level
        logger = logging.getLogger('')
        if daemon_options['LOG_FILE'] is None:
            handler = logging.StreamHandler(sys.stderr)
        else:
            handler = logging.FileHandler(daemon_options['LOG_FILE'])
        fmt = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        if self.log_prefix:
            fmt = self.log_prefix + ' ' + fmt
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, daemon_options['LOG_LEVEL'].upper()))
        return daemon_options

