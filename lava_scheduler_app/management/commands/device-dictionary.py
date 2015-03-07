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
# pylint: disable=invalid-name


import os
import sys
import jinja2
from optparse import make_option
from django.core.management.base import BaseCommand
from lava_scheduler_app.models import DeviceDictionary
from lava_scheduler_app.utils import devicedictionary_to_jinja2, jinja2_to_devicedictionary


def parse_template(device_file):

    if not os.path.exists(os.path.realpath(device_file)):
        print "Unable to find file '%s'\n" % device_file
        sys.exit(2)
    with open(device_file, 'r') as fileh:
        content = fileh.read()
    return jinja2_to_devicedictionary(content)


class Command(BaseCommand):

    logger = None
    # FIXME: migrate BaseCommand to argparse as optparse is deprecated
    # noinspection PyShadowingBuiltins
    help = "LAVA Device Dictionary I/O tool"
    option_list = BaseCommand.option_list + (
        make_option('--hostname', help="Hostname of the device to use"),
        make_option('--import', help="create new or update existing entry"),
        make_option(
            '--path',
            default='/etc/lava-server/dispatcher-config/',
            help='path to the lava-server jinja2 device type templates'),
        make_option(
            '--export',
            action="store_true",
            help="export existing entry"),
        make_option(
            '--review',
            action="store_true",
            help="review the generated device configuration")
    )

    def handle(self, *args, **options):
        """
        Accept options via lava-server manage which provides access
        to the database.
        """
        hostname = options['hostname']
        if hostname is None:
            print "Error: please specify a hostname"
        if options['import'] is not None:
            data = parse_template(options['import'])
            element = DeviceDictionary.get(hostname)
            if element is None:
                print "Adding new device dictionary for %s" % hostname
                element = DeviceDictionary(hostname=hostname)
                element.hostname = hostname
            element.parameters = data
            element.save()
            print "Device dictionary updated for %s" % hostname
        elif options['export'] is not None\
                or options['review'] is not None:
            element = DeviceDictionary.get(hostname)
            data = None
            if element is None:
                print "Unable to export - no dictionary found for '%s'" % hostname
            else:
                data = devicedictionary_to_jinja2(
                    element.parameters,
                    element.parameters['extends']
                )
            if options['review'] is None:
                print data
            else:
                string_loader = jinja2.DictLoader({'%s.yaml' % hostname: data})
                type_loader = jinja2.FileSystemLoader([
                    os.path.join(options['path'], 'device-types')])
                env = jinja2.Environment(
                    loader=jinja2.ChoiceLoader([string_loader, type_loader]),
                    trim_blocks=True)
                template = env.get_template("%s.yaml" % hostname)
                device_configuration = template.render()
                print device_configuration
        else:
            print "Error: please specify one of --import, --export or --review"
