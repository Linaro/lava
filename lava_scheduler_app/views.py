import json
import os

from django.http import HttpResponse
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
    log_file_present = os.path.exists(log_file_path)
    return render_to_response(
        "lava_scheduler_app/job.html",
        {
            'log_file_present': log_file_present,
            'job': TestJob.objects.get(pk=pk),
        },
        RequestContext(request))


LOG_CHUNK_SIZE = 20
NEWLINE_SCAN_SIZE = 4


def job_output(request, pk):
    start = int(request.GET.get('start', 0))
    job = TestJob.objects.get(pk=pk)
    log_file_path = '/tmp/lava-logs/job-%s.log' % job.id
    log_file = open(log_file_path, 'rb')
    log_file.seek(start)
    content = log_file.read(LOG_CHUNK_SIZE)
    if not content.endswith('\n'):
        extra_content = log_file.read(NEWLINE_SCAN_SIZE)
        if '\n' in extra_content:
            content += extra_content[:extra_content.index('\n')+1]
            if len(content) < len(extra_content):
                finished = False
            else:
                finished = not bool(log_file.read(1))
        else:
            finished = not bool(extra_content)
    else:
        finished = not bool(log_file.read(1))
    data = {
        'size': start + len(content),
        'is_finished': finished,
        'content': content,
        }
    return HttpResponse(json.dumps(data))
