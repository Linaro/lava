# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

# pylint gets confused: commands have no shebang, but the file is not a module.
# import order is a new pylint tag for putting system imports before package
# imports but there is no functional benefit.
# pylint: disable=invalid-name,wrong-import-order


import os
import sys
import yaml
from lava_server.utils import OptArgBaseCommand as BaseCommand
from lava_scheduler_app.models import DeviceDictionary, SubmissionException
from lava_scheduler_app.utils import (
    devicedictionary_to_jinja2,
    jinja2_to_devicedictionary,
    prepare_jinja_template,
)
from lava_scheduler_app.schema import validate_device


def parse_template(device_file):

    if not os.path.exists(os.path.realpath(device_file)):
        print "Unable to find file '%s'\n" % device_file
        sys.exit(2)
    with open(device_file, 'r') as fileh:
        content = fileh.read()
    return jinja2_to_devicedictionary(content)


class Command(BaseCommand):

    logger = None
    # noinspection PyShadowingBuiltins
    help = "LAVA Device Dictionary I/O tool"

    def add_arguments(self, parser):
        parser.add_argument('--hostname', help="Hostname of the device to use")
        parser.add_argument('--import', help="create new or update existing entry")
        parser.add_argument(
            '--path',
            default='/etc/lava-server/dispatcher-config/',
            help='path to the lava-server jinja2 device type templates')
        parser.add_argument(
            '--export',
            action="store_true",
            help="export existing entry")
        parser.add_argument(
            '--review',
            action="store_true",
            help="review the generated device configuration")

    def handle(self, *args, **options):
        """
        Accept options via lava-server manage which provides access
        to the database.
        """
        hostname = options['hostname']
        if hostname is None:
            self.stderr.write("Please specify a hostname")
            sys.exit(2)
        if options['import']:
            data = parse_template(options['import'])
            element = DeviceDictionary.get(hostname)
            if element is None:
                self.stdout.write("Adding new device dictionary for %s" %
                                  hostname)
                element = DeviceDictionary(hostname=hostname)
                element.hostname = hostname
            element.parameters = data
            element.save()
            self.stdout.write("Device dictionary updated for %s" % hostname)
        elif options['export'] or options['review']:
            element = DeviceDictionary.get(hostname)
            if element is None:
                self.stderr.write("Unable to export - no dictionary found for '%s'" %
                                  hostname)
                sys.exit(2)
            else:
                data = devicedictionary_to_jinja2(
                    element.parameters,
                    element.parameters['extends']
                )
            if not options['review']:
                self.stdout.write(data)
            else:
                template = prepare_jinja_template(hostname, data, system_path=False, path=options['path'])
                device_configuration = template.render()

                # validate against the device schema
                try:
                    validate_device(yaml.load(device_configuration))
                except (yaml.YAMLError, SubmissionException) as exc:
                    self.stderr.write("Invalid template: %s" % exc)

                self.stdout.write(device_configuration)
        else:
            self.stderr.write("Please specify one of --import, --export or --review")
            sys.exit(1)
