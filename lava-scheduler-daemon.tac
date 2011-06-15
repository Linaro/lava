import logging
import sys

from twisted.application import service
from twisted.application import internet
from twisted.python import filepath

from lava_scheduler_daemon.service import (
    LavaSchedulerService,
    DirectoryJobSource)

application = service.Application("lava scheduler daemon")

scheduler = LavaSchedulerService('fake-dispatcher')
source = DirectoryJobSource(filepath.FilePath('/tmp/lava-jobs'), 5, scheduler)
scheduler.job_source = source
scheduler.setServiceParent(application)
source.setServiceParent(application)

logger = logging.getLogger('')
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.DEBUG)

