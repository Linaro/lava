# -*- coding: utf-8 -*-
# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
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

from django.core.management.base import BaseCommand
from lava_results_app.models import Query, QueryMaterializedView


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
