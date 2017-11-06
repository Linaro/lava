# Copyright (C) 2017 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import csv
import yaml

from django.core.management.base import (
    BaseCommand,
    CommandParser
)

from django.core import serializers
from django.db.models import Q

from lava_scheduler_app.models import DeviceStateTransition, Device


class Command(BaseCommand):
    help = "Manage device state transitions."

    def add_arguments(self, parser):
        cmd = self

        class SubParser(CommandParser):
            """
            Sub-parsers constructor that mimic Django constructor.
            See http://stackoverflow.com/a/37414551
            """
            def __init__(self, **kwargs):
                super(SubParser, self).__init__(cmd, **kwargs)

        sub = parser.add_subparsers(dest="sub_command", help="Sub commands", parser_class=SubParser)

        # "export" sub-command
        export_parser = sub.add_parser("export", help="Export existing device state transitions")
        export_parser.add_argument("--old-state", default=None,
                                   choices=Device.STATUS_REVERSE.keys(),
                                   help="Filter output by old device status")
        export_parser.add_argument("--new-state", default=None,
                                   choices=Device.STATUS_REVERSE.keys(),
                                   help="Filter output by new device status")
        export_parser.add_argument("--csv", dest="csv", default=False,
                                   action="store_true", help="Print as csv, otherwise yaml by default")

    def handle(self, *args, **options):
        """ Forward to the right sub-handler """
        if options["sub_command"] == "export":
            self.handle_export(options["old_state"], options["new_state"],
                               options["csv"])

    def handle_export(self, old_state, new_state, format_as_csv):
        """ Output the device transitions """
        print(old_state, new_state, format_as_csv)

        condition = Q()
        if old_state:
            condition &= Q(old_state=Device.STATUS_REVERSE[old_state])
        if new_state:
            condition &= Q(new_state=Device.STATUS_REVERSE[new_state])

        transitions = DeviceStateTransition.objects.filter(condition)

        if format_as_csv:
            fields = ["created_on", "created_by", "device", "job",
                      "old_state", "new_state", "message"]
            writer = csv.DictWriter(self.stdout, fieldnames=fields)
            writer.writeheader()
            for transition in transitions:
                writer.writerow({
                    "created_on": transition.created_on,
                    "created_by": transition.created_by,
                    "device": transition.device.hostname,
                    "job": (transition.job.id if transition.job else None),
                    "old_state": transition.get_old_state_display(),
                    "new_state": transition.get_new_state_display(),
                    "message": transition.message
                })

        else:
            print(serializers.serialize("yaml", transitions))
