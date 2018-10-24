# -*- coding: utf-8 -*-
# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

import xmlrpc.client
from django.db import IntegrityError

from linaro_django_xmlrpc.models import ExposedV2API
from lava_scheduler_app.api import check_perm
from lava_scheduler_app.models import Alias


class SchedulerAliasesAPI(ExposedV2API):

    @check_perm("lava_scheduler_app.add_alias")
    def add(self, name):
        """
        Name
        ----
        `scheduler.aliases.add` (`name`)

        Description
        -----------
        [superuser only]
        Create a device-type alias

        Arguments
        ---------
        `name`: string
          Name of the alias

        Return value
        ------------
        None
        """
        try:
            Alias.objects.create(name=name)
        except IntegrityError as exc:
            raise xmlrpc.client.Fault(
                400, "Bad request: %s" % exc.message)

    @check_perm("lava_scheduler_app.delete_alias")
    def delete(self, name):
        """
        Name
        ----
        `scheduler.aliases.delete` (`name`)

        Description
        -----------
        [superuser only]
        Remove a device-type alias

        Arguments
        ---------
        `name`: string
          Name of the alias

        Return value
        ------------
        None
        """
        try:
            Alias.objects.get(name=name).delete()
        except Alias.DoesNotExist:
            raise xmlrpc.client.Fault(
                404, "Alias '%s' was not found." % name)

    def list(self):
        """
        Name
        ----
        `scheduler.aliases.list` ()

        Description
        -----------
        List available device-type aliases

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array of aliases
        """
        ret = []
        for alias in Alias.objects.all().order_by("name"):
            ret.append(alias.name)
        return ret

    def show(self, name):
        """
        Name
        ----
        `scheduler.aliases.show` (`name`)

        Description
        -----------
        Show alias details.

        Arguments
        ---------
        `name`: string
          Alias name

        Return value
        ------------
        This function returns an XML-RPC dictionary with alias details.
        """
        try:
            alias = Alias.objects.get(name=name)
        except Alias.DoesNotExist:
            raise xmlrpc.client.Fault(
                404, "Alias '%s' was not found." % name)

        device_types = []
        for dt in alias.device_types.all():
            if dt.owners_only and dt.some_devices_visible_to(self.user):
                continue
            device_types.append(dt.name)

        return {"name": alias.name,
                "device_types": device_types}
