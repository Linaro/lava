# -*- coding: utf-8 -*-
# Copyright (C) 2010-2018 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import sys

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import (
    HttpResponseForbidden,
    HttpResponseRedirect,
    HttpResponseServerError,
)
from django.shortcuts import render
from django.template import loader
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_POST

from lava_scheduler_app.models import ExtendedUser, RemoteArtifactsAuth
from lava_server.bread_crumbs import BreadCrumb, BreadCrumbTrail


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
