import logging.config
from optparse import make_option

from django.core.management.base import BaseCommand


class SchedulerCommand(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('-l', '--loglevel',
                    action='store',
                    default=None,
                    help="Log level, default is taken from settings."),
        make_option('-f', '--logfile',
                    action='store',
                    default=None,
                    help="Path to log file, default is taken from settings."),
        )

    log_prefix = ''


    _DEFAULT_LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'root': {
            'level': None,
            'handlers': ['default'],
        },
        'formatters': {
            'default': {
                'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'formatter': 'verbose'
            }
        },
    }


    def _configure(self, options):
        from django.conf import settings

        daemon_options = settings.SCHEDULER_DAEMON_OPTIONS.copy()
        if options['logfile'] is not None:
            daemon_options['LOG_FILE_PATH'] = options['logfile']
        if options['loglevel'] is not None:
            daemon_options['LOG_LEVEL'] = options['loglevel']

        if daemon_options['LOG_FILE_PATH'] in [None, '-']:
            handler = {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                }
        else:
            handler = {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': daemon_options['LOG_FILE_PATH'],
                'formatter': 'default'
                }

        fmt = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        if self.log_prefix:
            fmt = self.log_prefix + ' ' + fmt


        LOGGING = {
            'version': 1,
            'disable_existing_loggers': True,
            'root': {
                'level': daemon_options['LOG_LEVEL'].upper(),
                'handlers': ['default'],
            },
            'formatters': {'default': {'format': fmt}},
            'handlers': {'default': handler}
            }

        try:
            import lava.raven
        except ImportError:
            pass
        else:
            LOGGING['handlers']['sentry'] = {
                'level': 'ERROR',
                'class': 'raven.contrib.django.handlers.SentryHandler',
            }
            LOGGING['root']['handlers'].append('sentry')


        logging.config.dictConfig(LOGGING)

        return daemon_options

