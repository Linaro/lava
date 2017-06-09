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

import glob
import os
import xmlrpclib

from django.db import IntegrityError

from linaro_django_xmlrpc.models import ExposedAPI
from lava_scheduler_app.api import check_superuser
from lava_scheduler_app.models import Alias, DeviceType


class SchedulerDeviceTypesAPI(ExposedAPI):

    def _available_device_types(self):
        """ List avaiable device types by looking at the configuration files """
        available_types = []
        for fname in glob.iglob("/etc/lava-server/dispatcher-config/device-types/*.jinja2"):
            device_type = os.path.basename(fname[:-7])
            if not device_type.startswith("base"):
                available_types.append(device_type)
        available_types.sort()
        return available_types

    @check_superuser
    def add(self, name, description, display, owners_only,
            health_frequency, health_denominator):
        """
        Name
        ----
        `scheduler.device_types.add` (`name`, `description`, `display`, `owners_only`,
                                      `health_frequency`, health_denominator`)

        Description
        -----------
        [superuser only]
        Add a new device-type to the database. Devices will need a suitable
        template to use the new device-type.

        Arguments
        ---------
        `name`: string
          Name of the device-type
        `description`: string
          Device-type description
        `display`: bool
          Is the device-type displayed in the GUI?
        `owners_only`: bool
          Is the device-type only available to owners?
        `health_frequency`: int
          How often to run health checks
        `health_denominator`: string ("hours" or "jobs")
          Initiate health checks by hours or by jobs

        Return value
        ------------
        None
        """
        if health_denominator == "hours":
            health_denominator = DeviceType.HEALTH_PER_HOUR
        elif health_denominator == "jobs":
            health_denominator = DeviceType.HEALTH_PER_JOB
        else:
            raise xmlrpclib.Fault(
                400, "Bad request: invalid health_denominator.")

        try:
            DeviceType.objects.create(name=name, description=description,
                                      display=display, owners_only=owners_only,
                                      health_frequency=health_frequency,
                                      health_denominator=health_denominator)
        except IntegrityError:
            raise xmlrpclib.Fault(
                400, "Bad request: device-type name is already used.")

    @check_superuser
    def get_template(self, name):
        """
        Name
        ----
        `scheduler.device_types.get_template` (`tname`)

        Description
        -----------
        [superuser only]
        Return the device-type configuration

        Arguments
        ---------
        `name`: string
          Name of the device-type

        Return value
        ------------
        The device-type configuration
        """
        if name not in self._available_device_types():
            raise xmlrpclib.Fault(
                404, "Device-type '%s' was not found." % name)

        try:
            filename = os.path.join("/etc/lava-server/dispatcher-config/device-types", name)
            filename += ".jinja2"
            with open(filename, "r") as f_in:
                return xmlrpclib.Binary(f_in.read().encode("utf-8"))
        except IOError as exc:
            raise xmlrpclib.Fault(
                400, "Unable to read device-type configuration: %s" % exc.strerror)

    @check_superuser
    def set_template(self, name, config):
        """
        Name
        ----
        `scheduler.device_types.set_config` (`name`, `config`)

        Description
        -----------
        [superuser only]
        Set the device-type configuration

        Arguments
        ---------
        `name`: string
          name of the device-type
        `config`: string
          The device-type configuration as a jinja2 template

        Return value
        ------------
        None
        """
        # Validate the name (should not be a path)
        if name != os.path.basename(name):
            raise xmlrpclib.Fault(
                404, "Device-type '%s' is invalid" % name)

        try:
            filename = os.path.join("/etc/lava-server/dispatcher-config/device-types", name)
            filename += ".jinja2"
            with open(filename, "w") as f_out:
                f_out.write(config)
        except IOError as exc:
            raise xmlrpclib.Fault(
                400, "Unable to write device-type configuration: %s" % exc.strerror)

    def list(self, show_all=False):
        """
        Name
        ----
        `scheduler.device_types.list` (`show_all=False`)

        Description
        -----------
        List available device-types. Some device-types are only visible to
        devices owners.

        Arguments
        ---------
        `show_all`: bool
          Show all available device-types

        Return value
        ------------
        This function returns an XML-RPC array of device-types
        """
        available_types = self._available_device_types()
        device_types = [dt for dt in DeviceType.objects.all().order_by('name')
                        if not dt.owners_only or dt.some_devices_visible_to(self.user)]
        ret = []
        for dt in device_types:
            ret.append({"name": dt.name,
                        "devices": dt.device_set.count(),
                        "installed": True,
                        "template": dt.name in available_types})
        if show_all:
            device_type_names = [dt.name for dt in device_types]
            for dt_name in available_types:
                if dt_name not in device_type_names:
                    ret.append({"name": dt_name,
                                "devices": 0,
                                "installed": False,
                                "template": True})
        return ret

    def show(self, name):
        """
        Name
        ----
        `scheduler.device_types.show` (`name`)

        Description
        -----------
        Show some details about the given device type.

        Arguments
        ---------
        `name`: string
          Name of the device-type

        Return value
        ------------
        This function returns an XML-RPC dictionary with device-type details
        """

        try:
            dt = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Device-type '%s' was not found." % name)

        if dt.owners_only and not dt.some_devices_visible_to(self.user):
            raise xmlrpclib.Fault(
                404, "Device-type '%s' was not found." % name)

        aliases = [str(alias.name) for alias in dt.aliases.all()]
        devices = [str(d.hostname) for d in dt.device_set.all() if d.is_visible_to(self.user)]
        dt_dict = {"name": dt.name,
                   "description": dt.description,
                   "display": dt.display,
                   "owners_only": dt.owners_only,
                   "health_disabled": dt.disable_health_check,
                   "aliases": aliases,
                   "devices": devices}

        return dt_dict

    @check_superuser
    def update(self, name, description, display, owners_only, health_frequency,
               health_denominator, health_disabled):
        """
        Name
        ----
        `scheduler.device_types.update` (`name`, `description=None`,
                                         `display=None`, `owners_only=None`,
                                         `health_frequency=None`,
                                         `health_denominator=None`,
                                         `health_disabled=None`)

        Description
        -----------
        [superuser only]
        Update the metadata information for this device-type.

        Arguments
        ---------
        `name`: string
          Name of the device-type
        `description`: string
          Device-type description
        `display`: bool
          Is the device-type displayed in the GUI?
        `owners_only`: bool
          Hide this device type for all users except owners of devices of this type.
        `health_frequency`: int
          How often to run health checks
        `health_denominator`: string ("hours" or "jobs")
          Initiate health checks by hours or by jobs
        `health_disabled`: bool
          Disable health checks for this device-type

        Return value
        ------------
        None
        """
        try:
            dt = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Device-type '%s' was not found." % name)

        if description is not None:
            dt.description = description

        if display is not None:
            dt.display = display

        if owners_only is not None:
            dt.owners_only = owners_only

        if health_frequency is not None:
            dt.health_frequency = health_frequency

        if health_denominator is not None:
            if health_denominator == "hours":
                health_denominator = DeviceType.HEALTH_PER_HOUR
            elif health_denominator == "jobs":
                health_denominator = DeviceType.HEALTH_PER_JOB
            else:
                raise xmlrpclib.Fault(
                    400, "Bad request: invalid health_denominator.")

            dt.health_denominator = health_denominator

        if health_disabled is not None:
            dt.disable_health_check = health_disabled

        dt.save()


class SchedulerDeviceTypesAliasesAPI(ExposedAPI):

    @check_superuser
    def add(self, name, alias):
        """
        Name
        ----
        `scheduler.device_types.aliases.add` (`name`, `alias`)

        Description
        -----------
        [superuser only]
        Add an alias to the device-type

        Arguments
        ---------
        `name`: string
          Device-type name
        `alias`: string
          Alias name to add

        Return value
        ------------
        None
        """
        try:
            dt = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "DeviceType '%s' was not found." % name)

        alias_obj, _ = Alias.objects.get_or_create(name=alias)
        dt.aliases.add(alias_obj)
        dt.save()

    def list(self, name):
        """
        Name
        ----
        `scheduler.device_types.aliases.list` (`name`)

        Description
        -----------
        List device-type aliases

        Arguments
        ---------
        `name`: string
          Device-type name

        Return value
        ------------
        This function returns an XML-RPC array of aliases
        """
        try:
            dt = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "DeviceType '%s' was not found." % name)

        if dt.owners_only and not dt.some_devices_visible_to(self.user):
            raise xmlrpclib.Fault(
                404, "Device-type '%s' was not found." % name)

        return [a.name for a in dt.aliases.all().order_by("name")]

    @check_superuser
    def delete(self, name, alias):
        """
        Name
        ----
        `scheduler.device_types.aliases.delete` (`name`, `alias`)

        Description
        -----------
        [superuser only]
        Remove an alias from a device-type

        Arguments
        ---------
        `hostname`: string
          Device hostname
        `name`: string
          Alias to remove
        Return value
        ------------
        None
        """
        try:
            dt = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "DeviceType '%s' was not found." % name)

        try:
            alias_obj = Alias.objects.get(name=alias)
        except Alias.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Alias '%s' was not found." % name)

        dt.aliases.remove(alias_obj)
        dt.save()
