import logging
import os
import sys

from twisted.internet import reactor

from lava_scheduler_daemon.service import BoardSet

os.environ['DJANGO_SETTINGS_MODULE'] = 'lava_server.settings.development'
from lava_scheduler_daemon.dbjobsource import DatabaseJobSource

def main():
    source = DatabaseJobSource()

    if sys.argv[1:] == ['--use-fake']:
        dispatcher = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'fake-dispatcher')
    elif sys.argv[1:]:
        print >>sys.stderr, "invalid options %r" % sys.argv[1:]
        sys.exit(1)
    else:
        dispatcher = 'lava-dispatch'

    service = BoardSet(source, dispatcher, reactor)
    reactor.callWhenRunning(service.startService)

    logger = logging.getLogger('')
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    reactor.run()
