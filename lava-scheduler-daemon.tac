import logging
import sys

from twisted.application import service
from twisted.application import internet
from twisted.python import filepath
from twisted.internet import reactor

from lava_scheduler_daemon.service import BoardSet
from lava_scheduler_daemon.jobsource import DirectoryJobSource

application = service.Application("lava scheduler daemon")

source = DirectoryJobSource(filepath.FilePath('/tmp/lava-jobs'))
board_set = BoardSet(source, 'fake-dispatcher', reactor)
board_set.setServiceParent(application)

logger = logging.getLogger('')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

