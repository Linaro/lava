# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import xmlrpc.client

from django.db import IntegrityError
from django.forms import ValidationError

from lava_scheduler_app.api import check_perm
from lava_scheduler_app.models import Alias, DeviceType
from linaro_django_xmlrpc.models import ExposedV2API


class SchedulerAliasesAPI(ExposedV2API):
    @check_perm("lava_scheduler_app.add_alias")
    def add(self, name, device_type_name):
        """
        Name
        ----
        `scheduler.aliases.add` (`name`)

        Description
        -----------
        Create a device-type alias
        Permission: lava_scheduler_app.add_alias

        Arguments
        ---------
        `name`: string
          Name of the alias
        'device_type_name': string
          Name of the device type to alias

        Return value
        ------------
        None
        """
        try:
            dt = DeviceType.objects.get(name=device_type_name)
            if not self.user.has_perm(DeviceType.VIEW_PERMISSION, dt):
                raise xmlrpc.client.Fault(
                    404, "Device-type '%s' was not found." % device_type_name
                )
            alias = Alias(name=name, device_type=dt)
            alias.full_clean()
            alias.save()
        except ValidationError as e:
            raise xmlrpc.client.Fault(404, "\n".join(e.messages))
        except DeviceType.DoesNotExist:
            raise xmlrpc.client.Fault(400, "Bad request. DeviceType does not exist")
        except IntegrityError:
            raise xmlrpc.client.Fault(
                400, "Bad request. Alias or DeviceType name already exists."
            )

    @check_perm("lava_scheduler_app.delete_alias")
    def delete(self, name):
        """
        Name
        ----
        `scheduler.aliases.delete` (`name`)

        Description
        -----------
        Remove a device-type alias
        Permission: lava_scheduler_app.delete_alias

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
            raise xmlrpc.client.Fault(404, "Alias '%s' was not found." % name)

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
            raise xmlrpc.client.Fault(404, "Alias '%s' was not found." % name)

        dt = alias.device_type
        if dt is None or not self.user.has_perm(DeviceType.VIEW_PERMISSION, dt):
            return {"name": alias.name, "device_type": ""}

        return {"name": alias.name, "device_type": alias.device_type.name}
