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
    return render_to_response(
        "lava_scheduler_app/job.html",
        {
            'log_file_present': bool(job.log_file),
            'job': TestJob.objects.get(pk=pk),
        },
        RequestContext(request))


LOG_CHUNK_SIZE = 512*1024
NEWLINE_SCAN_SIZE = 80


def job_output(request, pk):
    start = int(request.GET.get('start', 0))
    count_present = 'count' in request.GET
    job = TestJob.objects.get(pk=pk)
    log_file = job.log_file
    log_file.seek(0, os.SEEK_END)
    size = int(request.GET.get('count', log_file.tell()))
    if size - start > LOG_CHUNK_SIZE and not count_present:
        log_file.seek(-LOG_CHUNK_SIZE, os.SEEK_END)
        content = log_file.read(LOG_CHUNK_SIZE)
        nl_index = content.find('\n', 0, NEWLINE_SCAN_SIZE)
        if nl_index > 0 and not count_present:
            content = content[nl_index + 1:]
        skipped = size - start - len(content)
    else:
        skipped = 0
        log_file.seek(start, os.SEEK_SET)
        content = log_file.read(size - start)
    nl_index = content.rfind('\n', -NEWLINE_SCAN_SIZE)
    if nl_index >= 0 and not count_present:
        content = content[:nl_index+1]
    response = HttpResponse(content)
    if skipped:
        response['X-Skipped-Bytes'] = str(skipped)
    response['X-Current-Size'] = str(start + len(content))
    if job.status != TestJob.RUNNING:
        response['X-Is-Finished'] = '1'
    return response
