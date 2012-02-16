import logging
import sys

from django.core.management.base import BaseCommand


class SchedulerCommand(BaseCommand):

    log_prefix = ''

    def _configure_logging(self, loglevel, logfile=None):
        logger = logging.getLogger('')
        if logfile is None:
            handler = logging.StreamHandler(sys.stderr)
        else:
            handler = logging.FileHandler(logfile)
        fmt = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        if self.log_prefix:
            fmt = self.log_prefix + ' ' + fmt
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, loglevel.upper()))

