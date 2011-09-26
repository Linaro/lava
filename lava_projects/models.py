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

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.query import QuerySet
from django.utils.translation import ugettext as _
from django_restricted_resource.managers import RestrictedResourceManager
from django_restricted_resource.models  import RestrictedResource


class ProjectQuerySet(QuerySet):
    """
    Query set with extra methods for projects
    """

    def recently_registered(self):
        return self.order_by("-registered_on")[:10]

    def get_by_identifier(self, identifier):
        """
        Get project by identifier, also searching for past
        identifiers (project renames)
        """
        try:
            return self.get(identifier=identifier)
        except Project.DoesNotExist as no_such_project:
            try:
                project_former_identifier = ProjectFormerIdentifier.objects.get(former_identifier=identifier)
                return project_former_identifier.project
            except ProjectFormerIdentifier.DoesNotExist:
                raise no_such_project


class ProjectManager(RestrictedResourceManager):
    """
    Manager with custom query set for projects
    """
    use_for_related_fields = True

    def get_query_set(self):
        return ProjectQuerySet(self.model, using=self._db)

    def recently_registered(self):
        return self.get_query_set().recently_registered()

    def get_by_identifier(self, identifier):
        return self.get_query_set().get_by_identifier(identifier)


class ProjectFormerIdentifier(models.Model):
    """
    Former identifier of a project. Allows users to change the project
    identifier while keeping URLs working properly.
    """

    project = models.ForeignKey(
        "Project",
        null=False,
        blank=False,
        verbose_name=_(u"Project"),
        related_name="former_identifiers")

    former_identifier = models.SlugField(
        null=False,
        blank=False,
        max_length=100,
        verbose_name=_(u"Former identifier"),
        help_text=_(u"A unique identifier built from restricted subset of"
                    u" characters (only basic letters, numbers and dash)"),
        unique=True)

    renamed_by = models.ForeignKey(
        User,
        related_name="project_former_identifiers_created",
        blank=False,
        null=False,
        verbose_name=_(u"Renamed by"),
        help_text=_(u"User who renamed the project"))

    renamed_on = models.DateTimeField(
        auto_now_add=True,
        blank=False,
        null=False,
        verbose_name=_(u"Renamed on"),
        help_text=_(u"Date and time of rename operation"))

    def __unicode__(self):
        return self.former_identifier


class Project(RestrictedResource):
    """
    Project is a container of everything else. Projects are restricted
    resources and thus belong to a particular user or group and have a "public"
    flag.
    """

    name = models.CharField(
        null=False,
        blank=False,
        max_length=100,
        verbose_name=_(u"Name"),
        help_text=_(u"Name (this is how your project will be displayed"
                    u" throughout LAVA)"))

    identifier = models.SlugField(
        null=False,
        blank=False,
        max_length=100,
        verbose_name=_(u"Identifier"),
        help_text=_(u"A unique identifier built from restricted subset of"
                    u" characters (only basic letters, numbers and dash)"),
        unique=True)

    description = models.TextField(
        null=False,
        blank=True,
        verbose_name = _(u"Description"),
        help_text = _(u"Arbitrary text about the project, you can use markdown"
                      u" formatting to style it"))

    is_aggregate = models.BooleanField(
        blank=True,
        null=False,
        verbose_name=_(u"Aggregate"),
        help_text=_(u"When selected the project will be treated like a"
                    u" distribution. Some UI elements are optimized for that case"
                    u" and behave differently."))

    registered_by = models.ForeignKey(
        User,
        related_name="projects",
        blank=False,
        null=False,
        verbose_name=_(u"Registered by"),
        help_text=_(u"User who registered this project"))

    registered_on = models.DateTimeField(
        auto_now_add=True,
        blank=False,
        null=False,
        verbose_name=_(u"Registered on"),
        help_text=_(u"Date and time of registration"))

    objects = ProjectManager()

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ('lava.project.detail', [self.identifier])
