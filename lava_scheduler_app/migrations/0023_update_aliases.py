# Copyright (C) 2016 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 1.10.3 on 2016-11-24 13:29
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0022_create_devicetype_alias")]

    operations = [
        migrations.AlterField(
            model_name="devicetype",
            name="aliases",
            field=models.ManyToManyField(
                blank=True, related_name="device_types", to="lava_scheduler_app.Alias"
            ),
        )
    ]
