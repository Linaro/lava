# Copyright (C) 2019 BayLibre
#
# Author: Corentin LABBE <clabbe@baylibre.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 1.11.23 on 2019-12-16 14:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0046_permission_consolidation")]

    operations = [
        migrations.AddField(
            model_name="worker", name="job_limit", field=models.IntegerField(default=0)
        )
    ]
