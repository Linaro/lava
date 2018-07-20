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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses>.


import sys
from django.core.management.base import BaseCommand
from lava_results_app.models import (
    Query,
    QueryMaterializedView
)


class Command(BaseCommand):
    """
    Provide lava-server manage option to drop all materialized views from
    database
    """

    logger = None
    help = "Drop materialized views from database"

    def handle(self, *args, **options):
        for query in Query.objects.all().filter(is_live=False):
            QueryMaterializedView.drop(query.id)
