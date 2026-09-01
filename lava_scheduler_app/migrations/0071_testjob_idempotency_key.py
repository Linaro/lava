# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0070_increase_tag_name_max_length")]

    operations = [
        migrations.AddField(
            model_name="testjob",
            name="idempotency_key",
            field=models.CharField(
                blank=True,
                default="",
                max_length=200,
                verbose_name="Idempotency key",
            ),
        ),
        migrations.AddConstraint(
            model_name="testjob",
            constraint=models.UniqueConstraint(
                condition=~models.Q(idempotency_key=""),
                fields=("submitter", "idempotency_key"),
                name="lava_scheduler_app_testjob_idempotency_key_uniq",
            ),
        ),
    ]
