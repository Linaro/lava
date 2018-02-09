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

import yaml
import sys

from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from linaro_django_xmlrpc.models import ExposedV2API
from lava_scheduler_app.api import check_superuser
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    Tag,
    Worker
)

if sys.version_info[0] == 2:
    # Python 2.x
    import xmlrpclib
elif sys.version_info[0] == 3:
    # For Python 3.0 and later
    import xmlrpc.client as xmlrpclib


class SchedulerDevicesAPI(ExposedV2API):

    @check_superuser
    def add(self, hostname, type_name, worker_hostname,
            user_name=None, group_name=None, public=True,
            health=None, description=None):
        """
        Name
        ----
        `scheduler.devices.add` (`hostname`, `type_name`, `worker_hostname`,
                                 `user_name=None`, `group_name=None`,
                                 `public=True`, `health=None`,
                                 `description=None`)

        Description
        -----------
        [superuser only]
        Add a new device to the database, to support V1 and V2.

        Each device will also need a device dictionary which may include a
        setting making the device exclusive to V2.

        Arguments
        ---------
        `hostname`: string
          Hostname of the device
        `type_name`: string
          Type of the new device
        `worker_hostname`: string
          Worker hostname
        `user_name`: string
          Device owner, None by default
        `group_name`: string
          Device group owner, None by default
        `public`: boolean
          Is the device public?
        `health`: string
          Device health, among ["GOOD", "UNKNOWN", "LOOPING", "BAD", "MAINTENANCE", "RETIRED"]
        `description`: string
          Device description

        Return value
        ------------
        None
        """
        user = group = None
        try:
            device_type = DeviceType.objects.get(name=type_name)
            worker = Worker.objects.get(hostname=worker_hostname)
            if user_name is not None:
                user = User.objects.get(username=user_name)
            if group_name is not None:
                group = Group.objects.get(name=group_name)
        except DeviceType.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "DeviceType '%s' was not found." % type_name)
        except Worker.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Worker '%s' was not found." % worker_hostname)
        except User.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "User '%s' was not found." % user_name)
        except Group.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Group '%s' was not found." % group_name)

        health_val = Device.HEALTH_UNKNOWN
        try:
            if health is not None:
                health_val = Device.HEALTH_REVERSE[health]
        except KeyError:
            raise xmlrpclib.Fault(
                400, "Invalid health")

        try:
            Device.objects.create(hostname=hostname, device_type=device_type,
                                  user=user, group=group, is_public=public,
                                  state=Device.STATE_IDLE, health=health_val,
                                  worker_host=worker, description=description)

        except (IntegrityError, ValidationError) as exc:
            raise xmlrpclib.Fault(
                400, "Bad request: %s" % exc.message)

    def get_dictionary(self, hostname, render=False, context=None):
        """
        Name
        ----
        `scheduler.devices.get_dictionary` (`hostname`, `render=False`, `context=None`)

        Support for the context argument is new in api_version 2
        see system.api_version().

        Description
        -----------
        Return the device configuration

        Arguments
        ---------
        `hostname`: string
          Hostname of the device
        `render`: bool
          Render the device configuration. By default, return the dictionary
        `context`: string
          Some device templates need a context specific when processing the
          device-type template. This can be specified as a YAML string.
          New in api_version 2 - see system.api_version()

        Return value
        ------------
        The device dictionary
        """
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Device '%s' was not found." % hostname)

        if not device.is_visible_to(self.user):
            raise xmlrpclib.Fault(
                403, "Device '%s' not available to user '%s'." %
                (hostname, self.user))

        job_ctx = None
        if context is not None:
            try:
                job_ctx = yaml.load(context)
            except yaml.YAMLError as exc:
                raise xmlrpclib.Fault(
                    400, "Job Context '%s' is not valid: %s" % (context, str(exc)))

        config = device.load_configuration(job_ctx=job_ctx,
                                           output_format="raw" if not render else "yaml")
        if config is None:
            raise xmlrpclib.Fault(
                404, "Device '%s' does not have a configuration" % hostname)
        return xmlrpclib.Binary(config.encode('utf-8'))

    @check_superuser
    def set_dictionary(self, hostname, dictionary):
        """
        Name
        ----
        `scheduler.devices.set_dictionary` (`hostname`, `dictionary`)

        Description
        -----------
        [superuser only]
        Set the device dictionary

        Arguments
        ---------
        `hostname`: string
          Hostname of the device
        `dictionary`: string
          The device dictionary as a jinja2 template

        Return value
        ------------
        True if the dictionary was saved to file, False otherwise.
        """
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Device '%s' was not found." % hostname)

        return device.save_configuration(dictionary)

    def list(self, show_all=False, offline_info=False):
        """
        Name
        ----
        `scheduler.devices.list` (`show_all=False`, `offline_info=False`)

        Description
        -----------
        List available devices with their state and type information.

        Arguments
        ---------
        `show_all`: boolean
          Show all devices, including retired
        `offline_info`: boolean
          Add date from which each of the returned devices is offline (if the
          device is offline) and the user who put the device offline (if the
          device is offline) to the returned dictionary.

        Return value
        ------------
        This function returns an XML-RPC array in which each item is a
        dictionary with device information
        """
        devices = Device.objects.all()
        if not show_all:
            devices = Device.objects.exclude(health=Device.HEALTH_RETIRED)
        devices = devices.order_by("hostname")

        ret = []
        for device in devices:
            if device.is_visible_to(self.user):
                current_job = device.current_job()
                device_dict = {"hostname": device.hostname,
                               "type": device.device_type.name,
                               "health": device.get_health_display(),
                               "state": device.get_state_display(),
                               "current_job": current_job.pk if current_job else None}
                ret.append(device_dict)

        return ret

    def show(self, hostname):
        """
        Name
        ----
        `scheduler.devices.show` (`hostname`)

        Description
        -----------
        Show some details about the given device.

        Arguments
        ---------
        `hostname`: string
          Hostname of the device

        Return value
        ------------
        This function returns an XML-RPC dictionary with device details
        """
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Device '%s' was not found." % hostname
            )

        if not device.is_visible_to(self.user):
            raise xmlrpclib.Fault(
                403, "Device '%s' not available to user '%s'." %
                (hostname, self.user)
            )

        current_job = device.current_job()
        device_dict = {"hostname": device.hostname,
                       "device_type": device.device_type.name,
                       "health": device.get_health_display(),
                       "state": device.get_state_display(),
                       "health_job": bool(device.get_health_check()),
                       "description": device.description,
                       "public": device.is_public,
                       "has_device_dict": bool(device.load_configuration(output_format="raw")),
                       "worker": None,
                       "user": device.user.username if device.user else None,
                       "group": device.group.name if device.group else None,
                       "current_job": current_job.pk if current_job else None,
                       "tags": [t.name for t in device.tags.all().order_by("name")]}
        if device.worker_host is not None:
            device_dict["worker"] = device.worker_host.hostname

        return device_dict

    @check_superuser
    def update(self, hostname, worker_hostname=None, user_name=None,
               group_name=None, public=True, health=None, description=None):
        """
        Name
        ----
        `scheduler.devices.update` (`hostname`, `worker_hostname=None`,
                                    `user_name=None`, `group_name=None`,
                                    `public=True`, `health=None`,
                                    `description=None`)

        Description
        -----------
        [superuser only]
        Update device parameters. Only the non-None values will be updated.
        Owner and group are always updated at the same time.

        Arguments
        ---------
        `hostname`: string
          Hostname of the device
        `worker_hostname`: string
          Worker hostname
        `user_name`: string
          Device owner
        `group_name`: string
          Device group owner
        `public`: boolean
          Is the device public?
        `health`: string
          Device health, among ["GOOD", "UNKNOWN", "LOOPING", "BAD", "MAINTENANCE", "RETIRED"]
        `description`: string
          Device description

        Return value
        ------------
        None
        """
        try:
            with transaction.atomic():
                device = Device.objects.get(hostname=hostname)

                if worker_hostname is not None:
                    try:
                        device.worker_host = Worker.objects.get(hostname=worker_hostname)
                    except Worker.DoesNotExist:
                        raise xmlrpclib.Fault(
                            404, "Unable to find worker '%s'" % worker_hostname)

                user = group = None
                try:
                    if user_name is not None:
                        user = User.objects.get(username=user_name)
                    if group_name is not None:
                        group = Group.objects.get(name=group_name)
                except User.DoesNotExist:
                    raise xmlrpclib.Fault(
                        404, "User '%s' was not found." % user_name)
                except Group.DoesNotExist:
                    raise xmlrpclib.Fault(
                        404, "Group '%s' was not found." % group_name)

                if user is not None or group is not None:
                    device.user = user
                    device.group = group

                if public is not None:
                    device.is_public = public

                try:
                    if health is not None:
                        device.health = Device.HEALTH_REVERSE[health]
                except KeyError:
                    raise xmlrpclib.Fault(
                        400, "Health '%s' is invalid" % health)

                if description is not None:
                    device.description = description

                device.save()
        except Device.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Device '%s' was not found." % hostname
            )
        except (IntegrityError, ValidationError) as exc:
            raise xmlrpclib.Fault(
                400, "Bad request: %s" % exc.message)


class SchedulerDevicesTagsAPI(ExposedV2API):

    @check_superuser
    def add(self, hostname, name):
        """
        Name
        ----
        `scheduler.devices.tags.add` (`hostname`, `name`)

        Description
        -----------
        [superuser only]
        Add a device tag to the specific device

        Arguments
        ---------
        `hostname`: string
          Device hostname
        `name`: string
          Tag name to add

        Return value
        ------------
        None
        """
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Device '%s' was not found." % hostname)

        tag, _ = Tag.objects.get_or_create(name=name)
        device.tags.add(tag)
        device.save()

    def list(self, hostname):
        """
        Name
        ----
        `scheduler.devices.tags.list` (`hostname`)

        Description
        -----------
        List device tags

        Arguments
        ---------
        `hostname`: string
          Device hostname

        Return value
        ------------
        This function returns an XML-RPC array of tag names
        """
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Device '%s' was not found." % hostname)

        return [t.name for t in device.tags.all()]

    @check_superuser
    def delete(self, hostname, name):
        """
        Name
        ----
        `scheduler.devices.tags.delete` (`hostname`, `name`)

        Description
        -----------
        [superuser only]
        Remove a device tag from the device

        Arguments
        ---------
        `hostname`: string
          Device hostname
        `name`: string
          Tag name to remove
        Return value
        ------------
        None
        """
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Device '%s' was not found." % hostname)

        try:
            tag = Tag.objects.get(name=name)
        except Tag.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Tag '%s' was not found." % name)

        device.tags.remove(tag)
        device.save()
