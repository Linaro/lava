# Copyright (C) 2023 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 3.2.19 on 2023-11-06 09:14

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lava_scheduler_app", "0058_add_testjob_view_performance_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="remoteartifactsauth",
            name="token",
            field=models.CharField(max_length=200, verbose_name="Token value"),
        ),
    ]
