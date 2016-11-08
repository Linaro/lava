# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

import sys
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponseServerError,
    HttpResponseForbidden,
    HttpResponseRedirect
)
from django.shortcuts import render
from django.template import loader
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import requires_csrf_token

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from lava_scheduler_app.models import ExtendedUser


class ExtendedUserIRCForm(forms.ModelForm):

    class Meta:
        model = ExtendedUser
        fields = ('irc_server', 'irc_handle', 'user')
        widgets = {'user': forms.HiddenInput}

    def __init__(self, *args, **kwargs):
        super(ExtendedUserIRCForm, self).__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        return super(ExtendedUserIRCForm, self).save(commit=commit, **kwargs)


@BreadCrumb(_("LAVA"))
def index(request):
    # Load and render the template
    return render(request, 'index.html',
                  {'bread_crumb_trail': BreadCrumbTrail.leading_to(index)})


@BreadCrumb(_("About you ({you})"),
            parent=index)
@login_required
def me(request):  # pylint: disable=invalid-name
    ExtendedUser.objects.get_or_create(user=request.user)
    data = {
        'irc_form': ExtendedUserIRCForm(instance=request.user.extendeduser),
        'bread_crumb_trail': BreadCrumbTrail.leading_to(
            me, you=request.user.get_full_name() or request.user.username),
    }
    return render(request, 'me.html', data)


@login_required
def update_irc_settings(request):

    extended_user = request.user.extendeduser
    if request.method == 'POST':
        form = ExtendedUserIRCForm(request.POST, instance=extended_user)
        if form.is_valid():
            extended_user = form.save()
            return HttpResponseRedirect(reverse('lava.me'))


@requires_csrf_token
def server_error(request, template_name='500.html'):
    exc_type, value, _ = sys.exc_info()
    context_dict = {
        'STATIC_URL': settings.STATIC_URL,
        'user': request.user,
        'request': request,
        'exception_type': exc_type,
        'exception_value': value
    }
    template = loader.get_template(template_name)
    return HttpResponseServerError(template.render(context_dict, request))


@requires_csrf_token
def permission_error(request, template_name='403.html'):
    template = loader.get_template(template_name)
    return HttpResponseForbidden(template.render({}, request))
