# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: GPL-2.0-or-later
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lava_scheduler_app", "0067_testjob_requested_device_and_worker"),
    ]

    operations = [
        migrations.AddField(
            model_name="testjob",
            name="metadata",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
    ]
