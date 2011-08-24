import json
import os

from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    )
from django.template import RequestContext
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render_to_response,
    )

from lava_scheduler_app.models import Device, TestJob


def post_only(func):
    def decorated(request, *args, **kwargs):
        if request.method != 'POST':
            return HttpResponseNotAllowed('Only POST here')
        return func(request, *args, **kwargs)
    return decorated


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
            'show_cancel': job.status <= TestJob.RUNNING and job.can_cancel(request.user),
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
    if job.status not in [TestJob.RUNNING, TestJob.CANCELING]:
        response['X-Is-Finished'] = '1'
    return response


@post_only
def job_cancel(request, pk):
    job = TestJob.objects.get(pk=pk)
    if job.can_cancel(request.user):
        job.cancel()
        return redirect('lava_scheduler_app.views.job', pk=job.pk)
    else:
        return HttpResponseForbidden(
            "you cannot cancel this job", content_type="text/plain")


def job_json(request, pk):
    job = get_object_or_404(TestJob, pk=pk)
    json_text = json.dumps({
        'status': job.get_status_display(),
        'results_link': job.results_link,
        })
    content_type = 'application/json'
    if 'callback' in request.GET:
        json_text = '%s(%s)'%(request.GET['callback'], json_text)
        content_type = 'text/javascript'
    return HttpResponse(json_text, content_type=content_type)


def device(request, pk):
    device = Device.objects.get(pk=pk)
    recent_jobs = TestJob.objects.all().filter(
        actual_device=device).order_by('-start_time')
    return render_to_response(
        "lava_scheduler_app/device.html",
        {
            'device': device,
            'recent_jobs': recent_jobs,
            'show_maintenance': device.can_admin(request.user) and \
                device.status in [Device.IDLE, Device.RUNNING],
            'show_online': device.can_admin(request.user) and \
                device.status in [Device.OFFLINE, Device.OFFLINING],
        },
        RequestContext(request))


@post_only
def device_maintenance_mode(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        device.put_into_maintenance_mode()
        return redirect('lava_scheduler_app.views.device', pk=device.pk)
    else:
        return HttpResponseForbidden(
            "you cannot administer this device", content_type="text/plain")


@post_only
def device_online(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        device.put_into_online_mode()
        return redirect('lava_scheduler_app.views.device', pk=device.pk)
    else:
        return HttpResponseForbidden(
            "you cannot administer this device", content_type="text/plain")
