# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 1.11.21 on 2019-09-13 10:27

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0043_auth_refactoring")]

    operations = [
        migrations.AlterModelOptions(
            name="testjob",
            options={
                "permissions": (
                    ("submit_testjob", "Can submit test job"),
                    ("cancel_resubmit_testjob", "Can cancel or resubmit test jobs"),
                )
            },
        )
    ]
