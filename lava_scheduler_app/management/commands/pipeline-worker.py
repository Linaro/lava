# Copyright (C) 2016 Linaro Limited
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

# pylint: disable=invalid-name,no-member

import sys
from lava_server.utils import OptArgBaseCommand as BaseCommand
from lava_scheduler_app.models import Worker


class Command(BaseCommand):
    """
    Very simple at this stage. More functionality to be added
    once the old worker support has been dropped.
    There is no benefit in having platform or environment details
    as these will not be updated.
    """

    logger = None
    help = "LAVA Pipeline worker helper"

    def add_arguments(self, parser):
        parser.add_argument('--hostname', help="Hostname of the new worker")
        parser.add_argument('--description', help='optional description of the new worker')
        # equivalent to turning off the display flag in the admin interface
        parser.add_argument(
            '--disable', action='store_true',
            help='prevent pipeline jobs running on this worker.')

    def handle(self, *args, **options):
        hostname = options['hostname']
        if hostname is None:
            self.stderr.write("Please specify a hostname")
            sys.exit(2)

        new_worker, created = Worker.objects.get_or_create(hostname=hostname)
        if not created:
            if new_worker.is_master:
                self.stderr.write("Error: %s is the master worker." % options['hostname'])
                sys.exit(1)
            self.stderr.write("Worker already exists with hostname %s" % options['hostname'])
            sys.exit(2)
        if options['description']:
            new_worker.description = options['description']
            new_worker.save(update_fields=['description'])
        if options['disable']:
            new_worker.display = False
            new_worker.save(update_fields=['display'])
        self.stdout.write("Worker %s created" % options['hostname'])
