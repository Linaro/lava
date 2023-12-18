# Copyright (C) 2016 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 1.9.4 on 2016-05-04 08:14
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_results_app", "0009_query_limit")]

    operations = [
        migrations.AlterField(
            model_name="query",
            name="is_changed",
            field=models.BooleanField(
                default=False, verbose_name="Conditions have changed"
            ),
        ),
        migrations.AlterField(
            model_name="query",
            name="is_updating",
            field=models.BooleanField(
                default=False,
                editable=False,
                verbose_name="Query is currently updating",
            ),
        ),
    ]
