# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0008_auto_20151014_1044")]

    operations = [
        migrations.AddField(
            model_name="testjob",
            name="pipeline_compatibility",
            field=models.IntegerField(default=0, editable=False),
            preserve_default=True,
        )
    ]
