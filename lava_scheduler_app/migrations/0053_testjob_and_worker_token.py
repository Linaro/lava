# Copyright (C) 2020 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 2.2.12 on 2020-05-26 08:09

from django.db import migrations, models

import lava_scheduler_app.models
from lava_scheduler_app.models import auth_token


def forwards_func(apps, schema_editor):
    Worker = apps.get_model("lava_scheduler_app", "Worker")
    for worker in Worker.objects.all():
        worker.token = auth_token()
        worker.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0052_device_is_synced")]

    operations = [
        migrations.AddField(
            model_name="worker",
            name="token",
            field=models.CharField(
                default=lava_scheduler_app.models.auth_token,
                help_text="Authorization token",
                max_length=32,
            ),
        ),
        migrations.RunPython(forwards_func, noop, elidable=True),
        migrations.AddField(
            model_name="testjob",
            name="token",
            field=models.CharField(
                default=lava_scheduler_app.models.auth_token,
                help_text="Authorization token",
                max_length=32,
            ),
        ),
    ]
