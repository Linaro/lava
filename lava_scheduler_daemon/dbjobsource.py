import json
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
        if device.status != Device.IDLE:
            return None
        jobs_for_device = TestJob.objects.all().filter(
            target=device, status=TestJob.SUBMITTED)
        jobs_for_device.order_by('submit_time')
        jobs = jobs_for_device[:1]
        if jobs:
            job = jobs[0]
            job.status = TestJob.RUNNING
            device.status = Device.RUNNING
            job.save()
            device.save()
            return json.loads(job.definition)
        else:
            return None

    @defer_to_thread
    def jobCompleted(self, board_name, log_stream):
        self.logger.debug('marking job as complete on %s', board_name)
        self.logger.debug('%s', log_stream.read())
        device = Device.objects.get(hostname=board_name)
        device.status = Device.IDLE
        job = TestJob.objects.get(target=device, status=TestJob.RUNNING)
        job.status = TestJob.COMPLETE
        device.save()
        job.save()
