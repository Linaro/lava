# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import django_tables2 as tables

from lava_results_app.models import Chart
from lava_server.lavatable import LavaTable


class UserChartTable(LavaTable):
    name = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    """
    )

    is_published = tables.Column()

    description = tables.Column()

    def render_description(self, value):
        value = " ".join(value.split(" ")[:15])
        return value.split("\n")[0]

    owner = tables.TemplateColumn(
        """
    {{ record.owner.username }}
    """
    )

    chart_group = tables.Column()

    view = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}/+detail">view</a>
    """
    )
    view.orderable = False

    remove = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}/+delete" data-toggle="confirm" data-title="Are you sure you want to delete this Chart?">remove</a>
    """
    )
    remove.orderable = False

    class Meta(LavaTable.Meta):
        model = Chart
        fields = (
            "name",
            "is_published",
            "description",
            "chart_group",
            "owner",
            "view",
            "remove",
        )
        sequence = fields
        searches = {"name": "contains", "description": "contains"}


class OtherChartTable(UserChartTable):
    name = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    """
    )

    description = tables.Column()

    def render_description(self, value):
        value = " ".join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserChartTable.Meta):
        fields = ("name", "description", "owner")
        sequence = fields
        exclude = ("is_published", "view", "remove", "chart_group")


class GroupChartTable(UserChartTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_columns["chart_group"].visible = False

    name = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    """
    )

    description = tables.Column()

    def render_description(self, value):
        value = " ".join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserChartTable.Meta):
        fields = ("name", "description", "owner")
        sequence = fields
