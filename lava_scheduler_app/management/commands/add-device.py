# Copyright (C) 2016 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os
import glob
from django.db.models import Q
from django.db.utils import IntegrityError
from django.core.management.base import BaseCommand

from lava_scheduler_app.models import Device, DeviceType, Worker


class Command(BaseCommand):
    help = "Adding device to this LAVA instance"

    def add_arguments(self, parser):
        parser.add_argument("devices", nargs="*",
                            help="A list of devices.")
        parser.add_argument("--list",
                            default=False,
                            action="store_true",
                            help="Listing installed device types")

        parser.add_argument("--device-type",
                            help="device type")
        opt = parser.add_argument_group("Device options")
        opt.add_argument("--non-pipeline", default=True,
                         action="store_false", dest="is_pipeline",
                         help="Is this a pipeline device? (True by default)")
        opt.add_argument("--offline", default=False,
                         action="store_true", dest="offline",
                         help="Create the device offline (Online by default)")
        opt.add_argument("--private", default=True,
                         action="store_false", dest="public",
                         help="Make this device private (Public by default)")
        opt.add_argument("--worker", default=None,
                         help="The worker host")

    def available_device_types(self):
        """
        List the available device types for V2
        """
        available_types = []
        for fname in glob.iglob("/etc/lava-server/dispatcher-config/device-types/*.jinja2"):
            device_type = os.path.basename(fname[:-7])
            if not device_type.startswith("base"):
                available_types.append(device_type)
        available_types.sort()
        return available_types

    def handle(self, *args, **options):
        self.stderr.write("This command is deprecated, use \"devices\" instead")

        # List the available device types if requested
        if options["list"]:
            v2_types = self.available_device_types()
            exclude = ['dynamic-vm']
            exclude.extend(v2_types)
            v1_types = DeviceType.objects.filter(~Q(name__in=exclude))
            self.stdout.write("Available V2 device types:")
            for device_type in v2_types:
                self.stdout.write("- %s" % device_type)
            self.stdout.write("Available V1 device types (deprecated):")
            for device_type in v1_types:
                self.stdout.write("- %s" % device_type.name)
            return

        # Check that we have at least one device type
        if len(options["devices"]) == 0:
            self.stderr.write("Device name not specified")
            return
        devices = options["devices"]
        devices.sort()

        # Check that heal-check can only be used with one device type
        if options["device_type"] is None:
            self.stderr.write("It is mandatory to specify a device type using '--device-type'")
            return

        # Check that the device-type does not clash
        if options["device_type"] == 'dynamic-vm':
            self.stderr.write("The 'dynamic-vm' device type is restricted to V1 only "
                              "and would be created automatically.")
            return

        if options["device_type"] not in self.available_device_types() and options["is_pipeline"]:
            self.stderr.write("V1 device types cannot be pipeline devices without a V2 template.")
            self.stderr.write("Use --non-pipeline or check the output of --list")
            return

        # Check that the worker does exists
        try:
            worker = Worker.objects.get(hostname=options["worker"])
        except Worker.DoesNotExist:
            if options["worker"] is not None:
                self.stderr.write("Unknown worker %s" % options["worker"])
                return
            worker = None

        # Check that the device type does not already exist
        try:
            device_type = DeviceType.objects.get(name=options["device_type"])
        except DeviceType.DoesNotExist:
            self.stderr.write("Unknown device type '%s' (see the available ones "
                              "using --list)" % options["device_type"])
            return

        # Compute the max length
        max_length = 0
        for device in devices:
            max_length = max(max_length, len(device))

        # Create the format string
        fmt_str = "- %%-%ds" % (max_length + 1)
        self.stdout.write("Adding the devices:")
        status = Device.IDLE if not options["offline"] else Device.OFFLINE
        for hostname in devices:
            self.stdout.write(fmt_str % hostname, ending="")
            try:
                device = Device.objects.create(hostname=hostname,
                                               device_type=device_type,
                                               worker_host=worker,
                                               is_pipeline=options["is_pipeline"],
                                               status=status,
                                               is_public=options["public"])
            except IntegrityError:
                self.stdout.write("[SKIP] error when creating the device %s" % hostname)
            else:
                self.stdout.write("[OK] %s" % device)
                if options["is_pipeline"]:
                    self.stdout.write("Remember to import a device dictionary "
                                      "before submitting test jobs or running "
                                      "health checks on %s." % device)
