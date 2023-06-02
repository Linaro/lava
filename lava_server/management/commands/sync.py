# Copyright (C) 2020 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib

import yaml
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from jinja2 import TemplateError as JinjaTemplateError
from jinja2.nodes import Assign as JinjaNodesAssign
from jinja2.nodes import Const as JinjaNodesConst
from jinja2.nodes import List as JinjaNodesList
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

from lava_common.exceptions import PermissionNameError
from lava_common.yaml import yaml_safe_load
from lava_scheduler_app import environment
from lava_scheduler_app.models import (
    Alias,
    Device,
    DeviceType,
    Group,
    GroupDevicePermission,
    Tag,
    User,
    Worker,
)
from lava_server.files import File


class Command(BaseCommand):
    help = "Sync device dictionaries to db records"

    SYNC_KEY = "sync_to_lava"

    def _parse_sync_dict(self, sync_dict):
        ret = {}
        if hasattr(sync_dict, "items"):
            for pair in sync_dict.items:
                if isinstance(pair.value, JinjaNodesList):
                    ret[pair.key.value] = [
                        [sub_node.value for sub_node in node.items]
                        if isinstance(node, JinjaNodesList)
                        else node.value
                        for node in pair.value.items
                    ]
                elif isinstance(pair.value, JinjaNodesConst):
                    ret[pair.key.value] = pair.value.value
                else:  # Ignore all other nodes
                    continue
        return ret

    def _parse_config(self, hostname):
        # Will raise OSError if the file does not exist.
        # Will raise jinja2.TemplateError if the template cannot be parsed.
        jinja_config = File("device", hostname).read()

        env = JinjaSandboxEnv(autoescape=False)
        ast = env.parse(jinja_config)
        return ast

    def _get_sync_to_lava(self, hostname):
        # Fetches value of the 'sync_to_lava' variable set in dictionary.
        try:
            config = self._parse_config(hostname)
        except (OSError, JinjaTemplateError) as exc:
            return None, exc

        sync = list(config.find_all(JinjaNodesAssign))
        for node in sync:
            with contextlib.suppress(AttributeError):
                if node.target.name == self.SYNC_KEY:
                    return node.node, None
        return None, None

    def handle(self, *_, **options):
        dicts = File("device").list("*.jinja2")
        synced_devices = []
        self.stdout.write("Scanning devices:")
        for name in dicts:
            hostname = name.rsplit(".", 1)[0]

            # Get value of 'sync_to_lava' variable from template.
            sync_dict, exc = self._get_sync_to_lava(hostname)

            if exc:
                self.stdout.write(f"* {hostname} [SKIP]")
                self.stdout.write(f"  -> invalid jinja2 template")
                self.stdout.write(f"  -> {exc}")
                continue

            if sync_dict is None:
                self.stdout.write(f"* {hostname} [SKIP]")
                self.stdout.write(f"  -> missing '{self.SYNC_KEY}'")
                continue

            # Convert it to dictionary.
            sync_dict = self._parse_sync_dict(sync_dict)

            try:
                template = environment.devices().get_template(name)
                yaml_safe_load(template.render())
            except JinjaTemplateError as exc:
                self.stdout.write(f"* {hostname} [SKIP]")
                self.stdout.write(f"  -> invalid jinja2 template")
                self.stdout.write(f"  -> {exc}")
                continue
            except yaml.YAMLError as exc:
                self.stdout.write(f"* {hostname} [SKIP]")
                self.stdout.write(f"  -> invalid yaml")
                self.stdout.write(f"  -> {exc}")
                continue

            # Check if this device is already manually created in db.
            with contextlib.suppress(Device.DoesNotExist):
                device = Device.objects.get(hostname=hostname)
                if not device.is_synced:
                    self.stdout.write(f"* {hostname} [SKIP]")
                    self.stdout.write(f"  -> created manually")
                    continue

            # Check keys
            if "device_type" not in sync_dict:
                self.stdout.write(f"* {hostname} [SKIP]")
                self.stdout.write(f"  -> 'device_type' is mandatory")
                continue

            # Add to managed devices list.
            self.stdout.write(f"* {hostname}")
            synced_devices.append(hostname)

            # Create device type. If not found, report an error and skip.
            device_type, created = DeviceType.objects.get_or_create(
                name=sync_dict["device_type"]
            )
            if created:
                self.stdout.write(f"  -> create device type: {device_type.name}")

            worker = None
            if "worker" in sync_dict:
                worker, created = Worker.objects.get_or_create(
                    hostname=sync_dict["worker"]
                )
                if created:
                    self.stdout.write(f"  -> create worker: {sync_dict['worker']}")

            # Create/update device.
            defaults = {
                "device_type": device_type,
                "description": "Created automatically by LAVA.",
                "worker_host": worker,
                "is_synced": True,
            }
            device, created = Device.objects.update_or_create(
                defaults, hostname=hostname
            )
            if created:
                Device.objects.filter(hostname=hostname).update(
                    health=Device.HEALTH_UNKNOWN
                )

            # Create aliases.
            for alias_name in sync_dict.get("aliases", []):
                Alias.objects.get_or_create(name=alias_name, device_type=device_type)
                self.stdout.write(f"  -> alias: {alias_name}")

            # Remove all tag relations first.
            device.tags.clear()
            # Create tags.
            for tag_name in sync_dict.get("tags", []):
                tag, _ = Tag.objects.get_or_create(name=tag_name)
                device.tags.add(tag)
                self.stdout.write(f"  -> tag: {tag_name}")

            # Link physical owner
            specified_owner = sync_dict.get("physical_owner", "")
            try:
                physical_owner = User.objects.get(username=specified_owner)
                device.physical_owner = physical_owner
                self.stdout.write(f"  -> user: {specified_owner}")
            except User.DoesNotExist:
                device.physical_owner = None
                if specified_owner:
                    self.stdout.write(f"  -> user '{specified_owner}' does not exist")
            finally:
                device.save()

            # Link physical group
            specified_group = sync_dict.get("physical_group", "")
            try:
                physical_group = Group.objects.get(name=specified_group)
                device.physical_group = physical_group
                self.stdout.write(f"  -> group: {specified_group}")
            except Group.DoesNotExist:
                device.physical_group = None
                if specified_group:
                    self.stdout.write(f"  -> group '{specified_group}' does not exist")
            finally:
                device.save()

            # Assign permission
            specified_permissions = sync_dict.get("group_device_permissions", [])
            for permission in specified_permissions:
                perm = permission[0]
                group = permission[1]

                try:
                    permission_group = Group.objects.get(name=group)
                    try:
                        GroupDevicePermission.objects.assign_perm(
                            perm, permission_group, device
                        )
                        self.stdout.write(
                            f"  -> add group permission: ({perm}, {group})"
                        )
                    except PermissionNameError:
                        self.stdout.write(f"  -> permission '{perm}' does not exist")
                except Group.DoesNotExist:
                    self.stdout.write(f"  -> group '{group}' does not exist")

            # Delete unused permission
            kwargs = {"device": device}
            obj_perm = GroupDevicePermission.objects.filter(**kwargs)
            for perm in obj_perm:
                if [
                    perm.permission.codename,
                    perm.group.name,
                ] not in specified_permissions:
                    GroupDevicePermission.objects.remove_perm(
                        perm.permission.codename, perm.group, perm.device
                    )
                    self.stdout.write(
                        f"  -> delete group permission: ({perm.permission.codename}, {perm.group.name})"
                    )

        # devices which have is_synced true if there's no device dict for them.
        Device.objects.filter(is_synced=True).exclude(
            hostname__in=synced_devices
        ).update(health=Device.HEALTH_RETIRED)

        # Device types which have all the devices synced and all of them retired
        # should become invisible.
        synced_retired_queryset = DeviceType.objects.annotate(
            not_synced_retired_count=Count(
                "device",
                filter=Q(device__is_synced=False)
                | ~Q(device__health=Device.HEALTH_RETIRED),
            )
        )
        synced_retired_queryset.filter(not_synced_retired_count=0).update(display=False)

        # Device types which have all the devices synced and some of them not
        # retired should become visible.
        synced_not_retired_queryset = DeviceType.objects.annotate(
            not_synced=Count(
                "device",
                filter=Q(device__is_synced=False),
            ),
            not_retired=Count(
                "device",
                filter=~Q(device__health=Device.HEALTH_RETIRED),
            ),
        )
        synced_not_retired_queryset.filter(not_synced=0).filter(
            not_retired__gt=0
        ).update(display=True)
