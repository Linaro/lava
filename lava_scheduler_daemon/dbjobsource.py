import logging

from twisted.internet.threads import deferToThread

from zope.interface import implements

from lava_scheduler_app.models import Device, TestJob
from lava_scheduler_daemon.jobsource import IJobSource


logger = logging.getLogger(__name__)


def defer_to_thread(func):
    def wrapper(*args, **kw):
        return deferToThread(func, *args, **kw)
    return wrapper


class DatabaseJobSource(object):

    implements(IJobSource)

    logger = logger.getChild('DirectoryJobSource')

    @defer_to_thread
    def getBoardList(self):
        return [d.hostname for d in Device.objects.all()]

    @defer_to_thread
    def getJobForBoard(self, board_name):
        device = Device.objects.get(hostname=board_name)
        jobs_for_device = TestJob.objects(target=device)
        jobs_for_device.order_by('submit_time')
        jobs = jobs_for_device[:1]
        if jobs:
            return jobs[0]
        else:
            return None

    @defer_to_thread
    def jobCompleted(self, board_name, log_stream):
        pass
