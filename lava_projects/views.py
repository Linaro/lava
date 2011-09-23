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

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.template import RequestContext, loader
from django.utils.translation import ugettext as _
from django.views.generic.list_detail import object_list, object_detail

from lava_projects.models import Project
from lava_projects.forms import ProjectForm


def project_root(request):
    template_name = "lava_projects/project_root.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {})
    return HttpResponse(t.render(c))


def project_list(request):
    return object_list(
        request,
        queryset=Project.objects.accessible_by_principal(request.user),
        template_name="lava_projects/project_list.html",
        template_object_name="project")


def project_detail(request, identifier):
    project = get_object_or_404(
        Project.objects.accessible_by_principal(request.user), 
        identifier=identifier)
    template_name = "lava_projects/project_detail.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'project': project,
        'belongs_to_user': project.is_owned_by(request.user),
    })
    return HttpResponse(t.render(c))


@login_required
def project_register(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        form.restrict_group_selection_for_user(request.user)
        if form.is_valid():
            project = Project.objects.create(
                name=form.cleaned_data['name'],
                identifier=form.cleaned_data['identifier'],
                description=form.cleaned_data['description'],
                is_aggregate=form.cleaned_data['is_aggregate'],
                owner=form.cleaned_data['group'] or request.user,
                is_public=form.cleaned_data['is_public'],
                registered_by=request.user)
            return HttpResponseRedirect(project.get_absolute_url())
    else:
        form = ProjectForm()
    template_name = "lava_projects/project_register_form.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'form': form,
        'submit_text': _(u"Register")
    })
    return HttpResponse(t.render(c))


@login_required
def project_update(request, identifier):
    project = get_object_or_404(
        Project.objects.accessible_by_principal(request.user), 
        identifier=identifier)
    if not project.is_owned_by(request.user):
        return HttpResponseForbidden("You cannot update this project")
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        form.restrict_group_selection_for_user(request.user)
        if form.is_valid():
            project.name = form.cleaned_data['name']
            project.identifier = form.cleaned_data['identifier']
            project.description = form.cleaned_data['description']
            project.is_aggregate = form.cleaned_data['is_aggregate']
            project.owner = form.cleaned_data['group'] or request.user
            project.is_public = form.cleaned_data['is_public']
            project.save()
            return HttpResponseRedirect(project.get_absolute_url())
    else:
        form = ProjectForm(initial=dict(
            name=project.name,
            identifier=project.identifier,
            description=project.description,
            is_aggregate=project.is_aggregate,
            group=project.group,
            is_public=project.is_public))
    template_name = "lava_projects/project_form.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'form': form,
        'submit_text': _(u"Update project")
    })
    return HttpResponse(t.render(c))
