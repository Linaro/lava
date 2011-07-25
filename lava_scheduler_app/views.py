import os

from django.template import RequestContext
from django.shortcuts import render_to_response

from lava_scheduler_app.models import Device, TestJob

def index(request):
    return render_to_response(
        "lava_scheduler_app/index.html",
        {
            'devices': Device.objects.all(),
            'jobs': TestJob.objects.filter(status__in=[
                TestJob.SUBMITTED, TestJob.RUNNING]),
        },
        RequestContext(request))


def alljobs(request):
    return render_to_response(
        "lava_scheduler_app/alljobs.html",
        {
            'jobs': TestJob.objects.all(),
        },
        RequestContext(request))


def job(request, pk):
    job = TestJob.objects.get(pk=pk)
    log_file_path = '/tmp/lava-logs/job-%s.log' % job.id
    if os.path.exists(log_file_path):
        log_file = open(log_file_path, 'rb')
    else:
        log_file = None
    return render_to_response(
        "lava_scheduler_app/job.html",
        {
            'log_file': log_file,
            'job': TestJob.objects.get(pk=pk),
        },
        RequestContext(request))
