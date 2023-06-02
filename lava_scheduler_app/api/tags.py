# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import xmlrpc.client

from django.db import IntegrityError

from lava_scheduler_app.api import check_perm
from lava_scheduler_app.models import Tag
from linaro_django_xmlrpc.models import ExposedV2API


class SchedulerTagsAPI(ExposedV2API):
    @check_perm("lava_scheduler_app.add_tag")
    def add(self, name, description=None):
        """
        Name
        ----
        `scheduler.tags.add` (`name`, `description=None`)

        Description
        -----------
        [superuser only]
        Create a device tag

        Arguments
        ---------
        `name`: string
          Name of the tag
        `description`: string
          Tag description

        Return value
        ------------
        None
        """
        try:
            Tag.objects.create(name=name, description=description)
        except IntegrityError:
            raise xmlrpc.client.Fault(400, "Bad request: tag already exists?")

    @check_perm("lava_scheduler_app.delete_tag")
    def delete(self, name):
        """
        Name
        ----
        `scheduler.tags.delete` (`name`)

        Description
        -----------
        [superuser only]
        Remove a device tag

        Arguments
        ---------
        `name`: string
          Name of the tag

        Return value
        ------------
        None
        """
        try:
            Tag.objects.get(name=name).delete()
        except Tag.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Tag '%s' was not found." % name)

    def list(self):
        """
        Name
        ----
        `scheduler.tags.list` ()

        Description
        -----------
        List available device tags

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array of tag dictionaries
        """
        ret = []
        for tag in Tag.objects.all().order_by("name"):
            ret.append({"name": tag.name, "description": tag.description})
        return ret

    def show(self, name):
        """
        Name
        ----
        `scheduler.tags.show` (`name`)

        Description
        -----------
        Show some details about the given device tag.

        Arguments
        ---------
        `name`: string
          Name of the device tag

        Return value
        ------------
        This function returns an XML-RPC dictionary with device tag details
        """
        try:
            tag = Tag.objects.get(name=name)
        except Tag.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Tag '%s' was not found." % name)

        devices = [d.hostname for d in tag.device_set.all() if d.can_view(self.user)]
        return {"name": name, "description": tag.description, "devices": devices}
