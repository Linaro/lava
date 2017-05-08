# Copyright (C) 2017 Linaro Limited
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

from django.core.management.base import BaseCommand

from lava_scheduler_app.models import TestJob
from lava_scheduler_app.utils import mkdir

import os


class Command(BaseCommand):
    help = "Move job outputs into the new location"

    def handle(self, *_, **options):
        base_dir = "/var/lib/lava-server/default/media/job-output/"
        len_base_dir = len(base_dir)
        jobs = TestJob.objects.all().order_by("id")

        self.stdout.write("Browsing all jobs")
        for job in jobs:
            self.stdout.write("* %d {%s => %s}" % (job.id, "job-%d" % job.id,
                                                   job.output_dir[len_base_dir:]))
            mkdir(os.path.dirname(job.output_dir))
            old_dir = base_dir + "job-%d" % job.id
            if not os.path.exists(old_dir):
                self.stdout.write("  -> no output directory")
                continue
            os.rename(old_dir, job.output_dir)
