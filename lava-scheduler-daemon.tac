import logging
import sys

from twisted.application import service
from twisted.application import internet
from twisted.python import filepath
from twisted.internet import reactor

from lava_scheduler_daemon.service2 import (
    BoardSet,
    DirectoryJobSource)

application = service.Application("lava scheduler daemon")

source = DirectoryJobSource(filepath.FilePath('/tmp/lava-jobs'))
board_set = BoardSet(source, 'fake-dispatcher', reactor)
board_set.setServiceParent(application)

logger = logging.getLogger('')
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.DEBUG)

