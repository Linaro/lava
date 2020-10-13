# -*- coding: utf-8 -*-
# Copyright (C) 2020 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
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

import contextlib
import jinja2
import yaml

from django.core.management.base import BaseCommand
from django.db.models import IntegerField, Case, When, Count, Q

from lava_common.compat import yaml_safe_load
from lava_server.files import File
import lava_scheduler_app.environment as environment
from lava_scheduler_app.models import Alias, Device, DeviceType, Tag, Worker


class Command(BaseCommand):
    help = "Sync device dictionaries to db records"

    SYNC_KEY = "sync_to_lava"

    def _parse_sync_dict(self, sync_dict):
        ret = {}
        if hasattr(sync_dict, "items"):
            for pair in sync_dict.items:
                if isinstance(pair.value, jinja2.nodes.List):
                    ret[pair.key.value] = [node.value for node in pair.value.items]
                elif isinstance(pair.value, jinja2.nodes.Const):
                    ret[pair.key.value] = pair.value.value
                else:  # Ignore all other nodes
                    continue
        return ret

    def _parse_config(self, hostname):
        # Will raise OSError if the file does not exist.
        # Will raise jinja2.TemplateError if the template cannot be parsed.
        jinja_config = File("device", hostname).read()

        env = jinja2.Environment(  # nosec - YAML, not HTML, no XSS scope.
            autoescape=False
        )
        ast = env.parse(jinja_config)
        return ast

    def _get_sync_to_lava(self, hostname):
        # Fetches value of the 'sync_to_lava' variable set in dictionary.
        try:
            config = self._parse_config(hostname)
        except (OSError, jinja2.TemplateError):
            return None

        sync = list(config.find_all(jinja2.nodes.Assign))
        for node in sync:
            with contextlib.suppress(AttributeError):
                if node.target.name == self.SYNC_KEY:
                    return node.node
        return None

    def handle(self, *_, **options):
        dicts = File("device").list("*.jinja2")
        synced_devices = []
        self.stdout.write("Scanning devices:")
        for name in dicts:
            hostname = name.rsplit(".", 1)[0]

            # Get value of 'sync_to_lava' variable from template.
            sync_dict = self._get_sync_to_lava(hostname)
            if sync_dict is None:
                self.stdout.write(f"* {hostname} [SKIP]")
                self.stdout.write(f"  -> missing '{self.SYNC_KEY}'")
                continue
            # Convert it to dictionary.
            sync_dict = self._parse_sync_dict(sync_dict)

            try:
                template = environment.devices().get_template(name)
                device_template = yaml_safe_load(template.render())
            except jinja2.TemplateError as exc:
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

        # devices which have is_synced true if there's no device dict for them.
        Device.objects.filter(is_synced=True).exclude(
            hostname__in=synced_devices
        ).update(health=Device.HEALTH_RETIRED)

        # Device types which have all the devices synced and all of them retired
        # should become invisible.
        dts = (
            DeviceType.objects.annotate(
                not_synced_retired_count=Count(
                    Case(
                        When(
                            Q(device__is_synced=False)
                            | ~Q(device__health=Device.HEALTH_RETIRED),
                            then=1,
                        ),
                        output_field=IntegerField(),
                    )
                )
            )
            .filter(not_synced_retired_count=0)
            .update(display=False)
        )
