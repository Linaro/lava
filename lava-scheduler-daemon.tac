import logging
import sys

from twisted.application import service
from twisted.application import internet
from twisted.python import filepath

from lava_scheduler_daemon.service import (
    LavaSchedulerService,
    DirectoryJobSource)

application = service.Application("pydoctor demo")

scheduler = LavaSchedulerService()
source = DirectoryJobSource(filepath.FilePath('/tmp/lava-jobs'), 5, scheduler)
scheduler.job_source = source
scheduler.setServiceParent(application)
source.setServiceParent(application)

logging.getLogger('').addHandler(logging.StreamHandler(sys.stdout))
logging.getLogger('').setLevel(logging.DEBUG)
