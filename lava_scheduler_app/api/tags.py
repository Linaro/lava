# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.

import sys

from django.db import IntegrityError

from linaro_django_xmlrpc.models import ExposedV2API
from lava_scheduler_app.api import check_superuser
from lava_scheduler_app.models import Tag

if sys.version_info[0] == 2:
    # Python 2.x
    import xmlrpclib
elif sys.version_info[0] == 3:
    # For Python 3.0 and later
    import xmlrpc.client as xmlrpclib


class SchedulerTagsAPI(ExposedV2API):

    @check_superuser
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
        except IntegrityError as exc:
            raise xmlrpclib.Fault(
                400, "Bad request: %s" % exc.message)

    @check_superuser
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
            raise xmlrpclib.Fault(
                404, "Tag '%s' was not found." % name)

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
            ret.append({"name": tag.name,
                        "description": tag.description})
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
            raise xmlrpclib.Fault(
                404, "Tag '%s' was not found." % name)

        devices = [d.hostname for d in tag.device_set.all() if d.is_visible_to(self.user)]
        return {"name": name,
                "description": tag.description,
                "devices": devices}
