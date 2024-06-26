# Copyright (C) 2023 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 3.2.19 on 2023-06-28 09:00

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("lava_scheduler_app", "0056_testjob_queue_timeout"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="device",
            options={
                "permissions": (("submit_to_device", "Can submit jobs to device"),)
            },
        ),
        migrations.AlterModelOptions(
            name="devicetype",
            options={
                "permissions": (
                    ("submit_to_devicetype", "Can submit jobs to device type"),
                )
            },
        ),
        migrations.RemoveField(
            model_name="worker",
            name="master_version_notified",
        ),
    ]
