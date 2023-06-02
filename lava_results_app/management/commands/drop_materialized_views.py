# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
