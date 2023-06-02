# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import os
import xmlrpc.client

from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.forms import ValidationError

from lava_scheduler_app.api import check_perm
from lava_scheduler_app.models import Alias, DeviceType, GroupDeviceTypePermission
from lava_server.api import check_staff
from lava_server.files import File
from linaro_django_xmlrpc.models import ExposedV2API


class SchedulerDeviceTypesAPI(ExposedV2API):
    def _available_device_types(self):
        """List available device types by looking at the configuration files"""
        available_types = []
        for device_type in File("device-type").list("*.jinja2"):
            if not device_type.startswith("base"):
                available_types.append(device_type[:-7])
        available_types.sort()
        return available_types

    @check_perm("lava_scheduler_app.change_devicetype")
    def add(
        self,
        name,
        description,
        display,
        owners_only,
        health_frequency,
        health_denominator,
    ):
        """
        Name
        ----
        `scheduler.device_types.add` (`name`, `description`, `display`, `owners_only`, `health_frequency`, health_denominator`)

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
          DEPRECATED: this field is not used any more
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
            raise xmlrpc.client.Fault(400, "Bad request: invalid health_denominator.")

        try:
            dt = DeviceType(
                name=name,
                description=description,
                display=display,
                health_frequency=health_frequency,
                health_denominator=health_denominator,
            )
            dt.full_clean()
            dt.save()
        except (IntegrityError, ValidationError):
            raise xmlrpc.client.Fault(
                400, "Bad request: device-type name is already used."
            )

    def get_health_check(self, name):
        """
        Name
        ----
        `scheduler.device_types.get_health_check` (`name`)

        Description
        -----------
        Return the health-check definition for the requested device-type or
        filename.

        Note: not all device-types have a health check filename that matches
        the device-type name in the database.

        Arguments
        ---------
        `name`: string
          Filename

        The .yaml suffix will be added if not specified.

        Return value
        ------------
        The health-check
        """
        with contextlib.suppress(DeviceType.DoesNotExist):
            dt = DeviceType.objects.get(name=name)
            if not dt.can_view(self.user):
                raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)

        # Filename should not be a path or starting with a dot
        if os.path.basename(name) != name or name[0] == ".":
            raise xmlrpc.client.Fault(400, "Invalid device-type '%s'" % name)

        try:
            return xmlrpc.client.Binary(
                File("health-check", name).read().encode("utf-8")
            )
        except FileNotFoundError:
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        except OSError as exc:
            raise xmlrpc.client.Fault(
                400, "Unable to read health-check: %s" % exc.strerror
            )

    def get_template(self, name):
        """
        Name
        ----
        `scheduler.device_types.get_template` (`name`)

        Description
        -----------
        Return the device-type configuration for the requested device-type or
        filename.

        Note: not all device-types have a health check filename that matches
        the device-type name in the database.

        Arguments
        ---------
        `name`: string
          Name of the device-type

        The .jinja2 suffix will be added if not specified.

        Return value
        ------------
        The device-type configuration
        """
        with contextlib.suppress(DeviceType.DoesNotExist):
            dt = DeviceType.objects.get(name=name)
            if not dt.can_view(self.user):
                raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)

        # Filename should not be a path or starting with a dot
        if os.path.basename(name) != name or name[0] == ".":
            raise xmlrpc.client.Fault(400, "Invalid device-type '%s'" % name)

        try:
            return xmlrpc.client.Binary(
                File("device-type", name).read().encode("utf-8")
            )
        except FileNotFoundError:
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        except OSError as exc:
            raise xmlrpc.client.Fault(
                400, "Unable to read device-type configuration: %s" % exc.strerror
            )

    @check_perm("lava_scheduler_app.change_devicetype")
    def set_health_check(self, name, config):
        """
        Name
        ----
        `scheduler.device_types.set_health_check` (`name`, `config`)

        Description
        -----------
        [superuser only]
        Set the health-check definition for the requested device-type or
        filename.

        Note: not all device-types have a health check filename that matches
        the device-type name in the database.

        Arguments
        ---------
        `name`: string
          name of the device-type
        `config`: string
          The health-check as a yaml file

        The .yaml suffix will be added if not specified.

        Return value
        ------------
        None
        """
        # Filename should not be a path or starting with a dot
        if os.path.basename(name) != name or name[0] == ".":
            raise xmlrpc.client.Fault(400, "Invalid device-type '%s'" % name)

        try:
            File("health-check", name).write(config)
        except OSError as exc:
            raise xmlrpc.client.Fault(
                400, "Unable to write health-check: %s" % exc.strerror
            )

    @check_perm("lava_scheduler_app.change_devicetype")
    def set_template(self, name, config):
        """
        Name
        ----
        `scheduler.device_types.set_template` (`name`, `config`)

        Description
        -----------
        [superuser only]
        Set the device-type configuration for the requested device-type or
        filename.

        Note: not all device-types have a health check filename that matches
        the device-type name in the database.

        Arguments
        ---------
        `name`: string
          name of the device-type
        `config`: string
          The device-type configuration as a jinja2 template

        The .jinja2 suffix will be added if not specified.

        Return value
        ------------
        None
        """
        # Filename should not be a path or starting with a dot
        if os.path.basename(name) != name or name[0] == ".":
            raise xmlrpc.client.Fault(400, "Invalid device-type '%s'" % name)

        try:
            File("device-type", name).write(config)
        except OSError as exc:
            raise xmlrpc.client.Fault(
                400, "Unable to write device-type configuration: %s" % exc.strerror
            )

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

        device_types = [
            dt
            for dt in DeviceType.objects.all()
            .visible_by_user(self.user)
            .prefetch_related("device_set")
            .order_by("name")
        ]
        ret = []
        for dt in device_types:
            ret.append(
                {
                    "name": dt.name,
                    "devices": dt.device_set.count(),
                    "installed": True,
                    "template": dt.name in available_types,
                }
            )
        if show_all:
            device_type_names = [dt.name for dt in device_types]
            for dt_name in available_types:
                if dt_name not in device_type_names:
                    ret.append(
                        {
                            "name": dt_name,
                            "devices": 0,
                            "installed": False,
                            "template": True,
                        }
                    )
        return ret

    @check_staff
    def perms_add(self, name, group, permission):
        try:
            dt = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        try:
            group = Group.objects.get(name=group)
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Group '%s' was not found." % group)
        GroupDeviceTypePermission.objects.assign_perm(permission, group, dt)

    @check_staff
    def perms_delete(self, name, group, permission):
        try:
            dt = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        try:
            group = Group.objects.get(name=group)
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Group '%s' was not found." % group)
        GroupDeviceTypePermission.objects.remove_perm(permission, group, dt)

    @check_staff
    def perms_list(self, name):
        try:
            dt = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)

        perms = GroupDeviceTypePermission.objects.filter(devicetype=dt)
        return [
            {
                "name": p.permission.codename,
                "group": p.group.name,
            }
            for p in perms
        ]

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
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        if not dt.can_view(self.user):
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)

        aliases = [str(alias.name) for alias in dt.aliases.all()]
        devices = [
            str(d.hostname) for d in dt.device_set.all() if d.can_view(self.user)
        ]
        dt_dict = {
            "name": dt.name,
            "description": dt.description,
            "display": dt.display,
            "health_disabled": dt.disable_health_check,
            "health_denominator": dt.get_health_denominator_display(),
            "health_frequency": dt.health_frequency,
            "aliases": aliases,
            "devices": devices,
            "default_template": not File("device-type", name).is_first(),
            "permissions": [
                {
                    "name": p.permission.codename,
                    "group": p.group.name,
                }
                for p in GroupDeviceTypePermission.objects.filter(devicetype=dt)
            ],
        }

        return dt_dict

    def update(
        self,
        name,
        description,
        display,
        owners_only,
        health_frequency,
        health_denominator,
        health_disabled,
    ):
        """
        Name
        ----
        `scheduler.device_types.update` (`name`, `description=None`,
                                         `display=None`,
                                         `owners_only=None`,
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
          DEPRECATED: this field is not used any more
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
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        if not dt.can_change(self.user):
            raise xmlrpc.client.Fault(
                403, "No 'admin' permissions for device-type '%s'." % name
            )

        if description is not None:
            dt.description = description

        if display is not None:
            dt.display = display

        if health_frequency is not None:
            dt.health_frequency = health_frequency

        if health_denominator is not None:
            if health_denominator == "hours":
                health_denominator = DeviceType.HEALTH_PER_HOUR
            elif health_denominator == "jobs":
                health_denominator = DeviceType.HEALTH_PER_JOB
            else:
                raise xmlrpc.client.Fault(
                    400, "Bad request: invalid health_denominator."
                )

            dt.health_denominator = health_denominator

        if health_disabled is not None:
            dt.disable_health_check = health_disabled

        dt.save()


class SchedulerDeviceTypesAliasesAPI(ExposedV2API):
    @check_perm("lava_scheduler_app.add_alias")
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
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        if not dt.can_change(self.user):
            raise xmlrpc.client.Fault(
                403, "No 'admin' permissions for device-type '%s'." % name
            )

        alias_obj, _ = Alias.objects.get_or_create(name=alias)
        dt.aliases.add(alias_obj)

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
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        if not dt.can_view(self.user):
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        return [a.name for a in dt.aliases.all().order_by("name")]

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
            raise xmlrpc.client.Fault(404, "Device-type '%s' was not found." % name)
        if not dt.can_change(self.user):
            raise xmlrpc.client.Fault(
                403, "No 'admin' permissions for device-type '%s'." % name
            )

        try:
            alias_obj = Alias.objects.get(name=alias)
        except Alias.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Alias '%s' was not found." % alias)

        dt.aliases.remove(alias_obj)
