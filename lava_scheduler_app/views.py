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
