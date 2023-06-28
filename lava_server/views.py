# Copyright (C) 2010-2018 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import base64
import sys

from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import render
from django.template import loader
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_POST

from lava_scheduler_app.dbutils import device_summary, device_type_summary
from lava_scheduler_app.models import ExtendedUser, RemoteArtifactsAuth, TestJob, Worker
from lava_server.bread_crumbs import BreadCrumb, BreadCrumbTrail
from linaro_django_xmlrpc.models import AuthToken


class ExtendedUserIRCForm(forms.ModelForm):
    class Meta:
        model = ExtendedUser
        fields = ("irc_server", "irc_handle", "user")
        widgets = {"user": forms.HiddenInput}


class ExtendedUserTableLengthForm(forms.ModelForm):
    class Meta:
        model = ExtendedUser
        fields = ("table_length", "user")
        widgets = {"user": forms.HiddenInput}


def healthz(request):
    try:
        User.objects.first()
        return JsonResponse({"health": "good"})
    except Exception:
        return JsonResponse(
            {"health": "bad", "error": "database connection lost"}, status=500
        )


def prometheus(request):
    # Authenticate using Basic auth
    if request.headers.get("Authorization"):
        auth = request.headers["Authorization"]
        if not auth.startswith("Basic "):
            return HttpResponseBadRequest("Only Basic authentication is supported")
        try:
            (name, secret) = (
                base64.standard_b64decode(auth[len("Basic ") :])
                .decode("utf-8")
                .split(":", 1)
            )
        except ValueError:
            return HttpResponseBadRequest("Invalid basic authentication")
        user = AuthToken.get_user_for_secret(name, secret)
        if user is None:
            return HttpResponseBadRequest("Unknown user")
        request.user = user

    data = ""

    (device_stats, running_jobs_count) = device_summary()
    data += f"""# TYPE devices_online counter
devices_online {device_stats['num_online']}
# TYPE devices_not_retired counter
devices_not_retired {device_stats['num_not_retired']}
# TYPE devices_running counter
devices_running {device_stats['active_devices']}
# TYPE jobs_running counter
jobs_running {running_jobs_count}
# TYPE devices_health_check_total counter
devices_health_check_total {device_stats['health_checks_total']}
# TYPE devices_health_check_complete counter
devices_health_check_complete {device_stats['health_checks_complete']}
"""

    # Device-types
    dts = device_type_summary(request.user).annotate(
        queued_jobs=Subquery(
            TestJob.objects.filter(
                Q(state=TestJob.STATE_SUBMITTED),
                Q(requested_device_type=OuterRef("device_type")),
            )
            .values("requested_device_type")
            .annotate(queued_jobs=Count("pk"))
            .values("queued_jobs"),
            output_field=IntegerField(),
        ),
    )
    data += "# TYPE device_type counter"
    for dt in dts:
        data += f"""
device_type{{name="{dt['device_type']}",state="idle"}} {dt['idle']}
device_type{{name="{dt['device_type']}",state="busy"}} {dt['busy']}
device_type{{name="{dt['device_type']}",state="offline"}} {dt['offline']}
device_type{{name="{dt['device_type']}",state="maintenance"}} {dt['maintenance']}
device_type{{name="{dt['device_type']}",state="queue"}} {dt['queued_jobs'] or 0}"""

    worker_stats = Worker.objects.exclude(health=Worker.HEALTH_RETIRED).aggregate(
        num_not_retired=Count("pk"),
        num_online=Count("pk", filter=Q(state=Worker.STATE_ONLINE)),
        num_offline=Count("pk", filter=Q(state=Worker.STATE_OFFLINE)),
        num_maintenance=Count("pk", filter=Q(health=Worker.HEALTH_MAINTENANCE)),
        num_active=Count("pk", filter=Q(health=Worker.HEALTH_ACTIVE)),
    )
    data += f"""
# TYPE workers_not_retired counter
workers_not_retired {worker_stats['num_not_retired']}
# TYPE workers_online counter
workers_online {worker_stats['num_online']}
# TYPE workers_offline counter
workers_offline {worker_stats['num_offline']}
# TYPE workers_maintenance counter
workers_maintenance {worker_stats['num_maintenance']}
# TYPE workers_active counter
workers_active {worker_stats['num_active']}
"""

    return HttpResponse(data, content_type="text/plain; version=0.0.4")


@BreadCrumb(_("LAVA"))
def index(request):
    # Load and render the template
    return render(
        request, "index.html", {"bread_crumb_trail": BreadCrumbTrail.leading_to(index)}
    )


@BreadCrumb(_("About you ({you})"), parent=index)
@login_required
def me(request):
    ExtendedUser.objects.get_or_create(user=request.user)
    data = {
        "irc_form": ExtendedUserIRCForm(instance=request.user.extendeduser),
        "table_length_form": ExtendedUserTableLengthForm(
            instance=request.user.extendeduser
        ),
        "bread_crumb_trail": BreadCrumbTrail.leading_to(
            me, you=request.user.get_full_name() or request.user.username
        ),
    }
    return render(request, "me.html", data)


@login_required
@require_POST
def update_irc_settings(request):
    extended_user = request.user.extendeduser
    form = ExtendedUserIRCForm(request.POST, instance=extended_user)
    if form.is_valid():
        extended_user = form.save()
    return HttpResponseRedirect(reverse("lava.me"))


@login_required
@requires_csrf_token
def update_remote_auth(request):
    if request.method == "POST":
        token_id = request.POST.get("id", None)
        token_name = request.POST.get("name", None)
        token_hash = request.POST.get("token", None)
        if not token_id:
            RemoteArtifactsAuth.objects.create(
                name=token_name, token=token_hash, user=request.user
            )
        else:
            token = RemoteArtifactsAuth.objects.get(pk=token_id)
            if token.user != request.user:
                raise PermissionDenied()
            token.name = token_name
            token.token = token_hash
            token.save()
        return HttpResponseRedirect(reverse("lava.me"))


@login_required
def delete_remote_auth(request, pk):
    token = RemoteArtifactsAuth.objects.get(pk=pk)
    if token.user != request.user:
        raise PermissionDenied()
    token.delete()
    return HttpResponseRedirect(reverse("lava.me"))


@login_required
@require_POST
def update_table_length_setting(request):
    extended_user = request.user.extendeduser
    form = ExtendedUserTableLengthForm(request.POST, instance=extended_user)
    if form.is_valid():
        extended_user = form.save()
    return HttpResponseRedirect(reverse("lava.me"))


@requires_csrf_token
def server_error(request, template_name="500.html"):
    exc_type, value, _ = sys.exc_info()
    context_dict = {
        "user": request.user,
        "request": request,
        "exception_type": exc_type,
        "exception_value": value,
    }
    template = loader.get_template(template_name)
    return HttpResponseServerError(template.render(context_dict, request))


@requires_csrf_token
def permission_error(request, exception, template_name="403.html"):
    template = loader.get_template(template_name)
    return HttpResponseForbidden(template.render({}, request))
