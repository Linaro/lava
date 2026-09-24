# Copyright (C) 2026 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lava_scheduler_app", "0071_lava_log_entry"),
    ]

    operations = [
        migrations.AddField(
            model_name="testjob",
            name="pool_pattern",
            field=models.CharField(
                blank=True,
                default=None,
                editable=False,
                max_length=200,
                null=True,
                verbose_name="Pool pattern",
            ),
        ),
    ]
