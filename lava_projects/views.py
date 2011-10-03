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
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, loader
from django.utils.translation import ugettext as _
from django.views.generic.list_detail import object_list, object_detail

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)
from lava_projects.models import (
    Project,
    ProjectFormerIdentifier,
)
from lava_projects.forms import (
    ProjectRenameForm,
    ProjectRegistrationForm,
    ProjectUpdateForm,
)


@BreadCrumb("Projects")
def project_root(request):
    template_name = "lava_projects/project_root.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'recent_project_list': Project.objects.accessible_by_principal(request.user).recently_registered(),
        'bread_crumb_trail': BreadCrumbTrail.leading_to(project_root)
    })
    return HttpResponse(t.render(c))


@BreadCrumb("List of all projects", project_root)
def project_list(request):
    return object_list(
        request,
        queryset=Project.objects.accessible_by_principal(request.user),
        template_name="lava_projects/project_list.html",
        extra_context={
            'bread_crumb_trail': BreadCrumbTrail.leading_to(project_list)
        },
        template_object_name="project")


@BreadCrumb("{project}", 
            parent=project_root,
            needs=['project_identifier'])
def project_detail(request, identifier):
    # A get by identifier, looking at renames, if needed.
    try:
        project = Project.objects.accessible_by_principal(request.user).get_by_identifier(identifier)
    except Project.DoesNotExist:
        raise Http404("No such project")
    # Redirect users to proper URL of this project if using one of the older names.
    if project.identifier != identifier:
        return HttpResponseRedirect(project.get_absolute_url() + "?former_identifier=" + identifier)
    # Lookup former identifier if we have been redirected
    former_identifier = None
    if request.GET.get("former_identifier"):
        try:
            former_identifier = ProjectFormerIdentifier.objects.get(
                former_identifier=request.GET.get("former_identifier"))
        except ProjectFormerIdentifier.DoesNotExist:
            pass
    # Render to template
    template_name = "lava_projects/project_detail.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'project': project,
        'former_identifier': former_identifier, 
        'belongs_to_user': project.is_owned_by(request.user),
        'bread_crumb_trail': BreadCrumbTrail.leading_to(
            project_detail,
            project=project,
            project_identifier=project.identifier)
    })
    return HttpResponse(t.render(c))


@BreadCrumb("Register new project",
            parent=project_root)
@login_required
def project_register(request):
    if request.method == 'POST':
        form = ProjectRegistrationForm(request.POST, request.FILES)
        form.restrict_group_selection_for_user(request.user)
        # Check the form
        if form.is_valid():
            # And make a project instance
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
        form = ProjectRegistrationForm()
    # Render to template
    template_name = "lava_projects/project_register_form.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'form': form,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(project_register),
    })
    return HttpResponse(t.render(c))


@BreadCrumb("Reconfigure",
            parent=project_detail,
            needs=['project_identifier'])
@login_required
def project_update(request, identifier):
    project = get_object_or_404(
        Project.objects.accessible_by_principal(request.user), 
        identifier=identifier)
    if not project.is_owned_by(request.user):
        return HttpResponseForbidden("You cannot update this project")
    if request.method == 'POST':
        form = ProjectUpdateForm(request.POST, request.FILES)
        form.restrict_group_selection_for_user(request.user)
        if form.is_valid():
            project.name = form.cleaned_data['name']
            project.description = form.cleaned_data['description']
            project.is_aggregate = form.cleaned_data['is_aggregate']
            project.owner = form.cleaned_data['group'] or request.user
            project.is_public = form.cleaned_data['is_public']
            project.save()
            return HttpResponseRedirect(project.get_absolute_url())
    else:
        form = ProjectUpdateForm(initial=dict(
            name=project.name,
            description=project.description,
            is_aggregate=project.is_aggregate,
            group=project.group,
            is_public=project.is_public))
    template_name = "lava_projects/project_update_form.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'form': form,
        'project': project,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(
            project_update,
            project=project,
            project_identifier=project.identifier)
    })
    return HttpResponse(t.render(c))


@BreadCrumb("Change identifier",
            parent=project_update,
            needs=['project_identifier'])
@login_required
def project_rename(request, identifier):
    project = get_object_or_404(
        Project.objects.accessible_by_principal(request.user), 
        identifier=identifier)
    if not project.is_owned_by(request.user):
        return HttpResponseForbidden("You cannot update this project")
    if request.method == 'POST':
        form = ProjectRenameForm(project, request.POST)
        if form.is_valid():
            # Remove old entry if we are reusing our older identifier 
            pfi = ProjectFormerIdentifier.objects.filter(
                former_identifier=form.cleaned_data['identifier'],
                project=project.pk).delete()
            # Record the change taking place
            ProjectFormerIdentifier.objects.create(
                project=project,
                former_identifier=project.identifier,
                renamed_by=request.user)
            # And update the project
            project.name = form.cleaned_data['name']
            project.identifier = form.cleaned_data['identifier']
            project.save()
            return HttpResponseRedirect(project.get_absolute_url())
    else:
        form = ProjectRenameForm(
            project, initial={
                'name': project.name,
                'identifier': project.identifier})
    template_name = "lava_projects/project_rename_form.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'form': form,
        'project': project,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(
            project_rename,
            project=project,
            project_identifier=project.identifier)
    })
    return HttpResponse(t.render(c))
