# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0006_auto_20150619_1035")]

    operations = [
        migrations.AddField(
            model_name="devicetype",
            name="description",
            field=models.TextField(
                default=None,
                max_length=200,
                null=True,
                verbose_name="Device Type Description",
                blank=True,
            ),
            preserve_default=True,
        )
    ]
