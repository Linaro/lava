# Copyright (C) 2020 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 1.11.28 on 2020-05-28 10:58

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0051_worker_master_version_notified")]

    operations = [
        migrations.AddField(
            model_name="device",
            name="is_synced",
            field=models.BooleanField(
                default=False,
                help_text="Is this device synced from device dictionary or manually created.",
            ),
        )
    ]
