# Copyright (C) 2026 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("lava_scheduler_app", "0073_testjob_view_permission_and_device_id_index"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="testjob",
            options={"default_permissions": ("change", "delete", "view")},
        ),
    ]
