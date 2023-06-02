# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import xmlrpc.client

import yaml
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q

from lava_common.yaml import yaml_safe_load
from lava_scheduler_app.api import check_perm
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    GroupDevicePermission,
    Tag,
    TestJob,
    Worker,
)
from lava_server.api import check_staff
from linaro_django_xmlrpc.models import ExposedV2API


class SchedulerDevicesAPI(ExposedV2API):
    @check_perm("lava_scheduler_app.change_device")
    def add(
        self,
        hostname,
        type_name,
        worker_hostname,
        user_name=None,
        group_name=None,
        public=True,
        health=None,
        description=None,
    ):
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
        Add a new device to the database, to support V2.

        Each device will also need a device dictionary.

        Arguments
        ---------
        `hostname`: string
          Hostname of the device
        `type_name`: string
          Type of the new device
        `worker_hostname`: string
          Worker hostname
        `user_name`: string
          DEPRECATED: This field is not used any more
        `group_name`: string
          DEPRECATED: This field is not used any more
        `public`: boolean
          DEPRECATED: This field is not used any more
        `health`: string
          Device health, among ["GOOD", "UNKNOWN", "LOOPING", "BAD", "MAINTENANCE", "RETIRED"]
        `description`: string
          Device description

        Return value
        ------------
        None
        """
        try:
            device_type = DeviceType.objects.get(name=type_name)
            worker = Worker.objects.get(hostname=worker_hostname)
        except DeviceType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "DeviceType '%s' was not found." % type_name)
        except Worker.DoesNotExist:
            raise xmlrpc.client.Fault(
                404, "Worker '%s' was not found." % worker_hostname
            )

        health_val = Device.HEALTH_UNKNOWN
        try:
            if health is not None:
                health_val = Device.HEALTH_REVERSE[health]
        except KeyError:
            raise xmlrpc.client.Fault(400, "Invalid health")

        try:
            Device.objects.create(
                hostname=hostname,
                device_type=device_type,
                state=Device.STATE_IDLE,
                health=health_val,
                worker_host=worker,
                description=description,
            )

        except (IntegrityError, ValidationError):
            raise xmlrpc.client.Fault(400, "Bad request: device already exists?")

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
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)

        if not device.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Device '%s' not available to user '%s'." % (hostname, self.user)
            )

        job_ctx = None
        if context is not None:
            try:
                job_ctx = yaml_safe_load(context)
            except yaml.YAMLError as exc:
                raise xmlrpc.client.Fault(
                    400, "Job Context '%s' is not valid: %s" % (context, str(exc))
                )

        config = device.load_configuration(
            job_ctx=job_ctx, output_format="raw" if not render else "yaml"
        )
        if config is None:
            raise xmlrpc.client.Fault(
                404, "Device '%s' does not have a configuration" % hostname
            )
        return xmlrpc.client.Binary(config.encode("utf-8"))

    def set_dictionary(self, hostname, dictionary):
        """
        Name
        ----
        `scheduler.devices.set_dictionary` (`hostname`, `dictionary`)

        Description
        -----------
        [user with admin permission only]
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
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)

        if not device.can_change(self.user):
            raise xmlrpc.client.Fault(
                403,
                "User '%s' needs admin permission on device %s."
                % (self.user, hostname),
            )

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
        devices = (
            Device.objects.all()
            .visible_by_user(self.user)
            .select_related("device_type")
            .prefetch_related(
                Prefetch(
                    "testjobs",
                    queryset=TestJob.objects.filter(~Q(state=TestJob.STATE_FINISHED)),
                    to_attr="running_jobs",
                )
            )
        )
        if not show_all:
            devices = devices.exclude(health=Device.HEALTH_RETIRED)
        devices = devices.order_by("hostname")

        ret = []
        for device in devices:
            current_job = device.current_job()
            device_dict = {
                "hostname": device.hostname,
                "type": device.device_type.name,
                "health": device.get_health_display(),
                "state": device.get_state_display(),
                "current_job": current_job.pk if current_job else None,
                "pipeline": True,
            }
            ret.append(device_dict)

        return ret

    @check_staff
    def perms_add(self, hostname, group, permission):
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)
        try:
            group = Group.objects.get(name=group)
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Group '%s' was not found." % group)
        GroupDevicePermission.objects.assign_perm(permission, group, device)

    @check_staff
    def perms_delete(self, hostname, group, permission):
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)
        try:
            group = Group.objects.get(name=group)
        except Group.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Group '%s' was not found." % group)
        GroupDevicePermission.objects.remove_perm(permission, group, device)

    @check_staff
    def perms_list(self, hostname):
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)

        perms = GroupDevicePermission.objects.filter(device=device)
        return [
            {
                "name": p.permission.codename,
                "group": p.group.name,
            }
            for p in perms
        ]

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
            device = Device.objects.select_related("device_type", "worker_host").get(
                hostname=hostname
            )
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)

        if not device.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Device '%s' not available to user '%s'." % (hostname, self.user)
            )

        current_job = device.current_job()
        device_dict = {
            "hostname": device.hostname,
            "device_type": device.device_type.name,
            "health": device.get_health_display(),
            "state": device.get_state_display(),
            "health_job": bool(device.get_health_check()),
            "description": device.description,
            "pipeline": True,
            "has_device_dict": bool(device.load_configuration(output_format="raw")),
            "worker": None,
            "current_job": current_job.pk if current_job else None,
            "tags": [t.name for t in device.tags.all().order_by("name")],
            "permissions": [
                {
                    "name": p.permission.codename,
                    "group": p.group.name,
                }
                for p in GroupDevicePermission.objects.filter(device=device)
            ],
        }
        if device.worker_host is not None:
            device_dict["worker"] = device.worker_host.hostname

        return device_dict

    def update(
        self,
        hostname,
        worker_hostname=None,
        user_name=None,
        group_name=None,
        public=True,
        health=None,
        description=None,
        device_type=None,
    ):
        """
        Name
        ----
        `scheduler.devices.update` (`hostname`, `worker_hostname=None`,
                                    `user_name=None`, `group_name=None`,
                                    `public=True`,  `health=None`,
                                    `description=None`, `device_type=None`)

        Description
        -----------
        [user with admin permission only]
        Update device parameters. Only the non-None values will be updated.
        Owner and group are always updated at the same time.

        Arguments
        ---------
        `hostname`: string
          Hostname of the device
        `worker_hostname`: string
          Worker hostname
        `user_name`: string
          DEPRECATED: This field is not used any more
        `group_name`: string
          DEPRECATED: This field is not used any more
        `public`: boolean
          DEPRECATED: This field is not used any more
        `health`: string
          Device health, among ["GOOD", "UNKNOWN", "LOOPING", "BAD", "MAINTENANCE", "RETIRED"]
        `description`: string
          Device description
        `device_type`: string
          Device type

        Return value
        ------------
        None
        """
        try:
            with transaction.atomic():
                device = Device.objects.get(hostname=hostname)

                if not device.can_change(self.user):
                    raise xmlrpc.client.Fault(
                        403,
                        "User '%s' needs admin permission on device %s."
                        % (self.user, hostname),
                    )

                if worker_hostname is not None:
                    try:
                        device.worker_host = Worker.objects.get(
                            hostname=worker_hostname
                        )
                    except Worker.DoesNotExist:
                        raise xmlrpc.client.Fault(
                            404, "Unable to find worker '%s'" % worker_hostname
                        )

                try:
                    if health is not None:
                        prev_health = device.get_health_display()
                        device.health = Device.HEALTH_REVERSE[health]
                        device.log_admin_entry(
                            self.user,
                            "%s → %s (xmlrpc api)"
                            % (prev_health, device.get_health_display()),
                        )
                except KeyError:
                    raise xmlrpc.client.Fault(400, "Health '%s' is invalid" % health)

                if description is not None:
                    device.description = description

                if device_type is not None:
                    try:
                        device.device_type = DeviceType.objects.get(name=device_type)
                    except DeviceType.DoesNotExist:
                        raise xmlrpc.client.Fault(
                            404, "Unable to find device-type '%s'" % device_type
                        )
                device.save()
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)
        except (IntegrityError, ValidationError):
            raise xmlrpc.client.Fault(400, "Bad request")

    @check_perm("lava_scheduler_app.delete_device")
    def delete(self, hostname):
        """
        Name
        ----
        `scheduler.devices.delete` (`hostname`)

        Description
        -----------
        Remove a device.

        Arguments
        ---------
        `hostname`: string
          Hostname of the device

        Return value
        ------------
        None
        """
        try:
            Device.objects.get(hostname=hostname).delete()
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)


class SchedulerDevicesTagsAPI(ExposedV2API):
    @check_perm("lava_scheduler_app.add_tag")
    def add(self, hostname, name):
        """
        Name
        ----
        `scheduler.devices.tags.add` (`hostname`, `name`)

        Description
        -----------
        [user with admin device and add tag permissions only]
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
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)
        if not device.can_change(self.user):
            raise xmlrpc.client.Fault(
                403,
                "User '%s' needs admin permission on device %s."
                % (self.user, hostname),
            )

        tag, _ = Tag.objects.get_or_create(name=name)
        device.tags.add(tag)

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
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)

        return [t.name for t in device.tags.all()]

    def delete(self, hostname, name):
        """
        Name
        ----
        `scheduler.devices.tags.delete` (`hostname`, `name`)

        Description
        -----------
        [user with admin permission only]
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
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)

        if not device.can_change(self.user):
            raise xmlrpc.client.Fault(
                403,
                "User '%s' needs admin permission on device %s."
                % (self.user, hostname),
            )

        try:
            tag = Tag.objects.get(name=name)
        except Tag.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Tag '%s' was not found." % name)

        device.tags.remove(tag)
