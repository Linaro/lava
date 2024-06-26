# Copyright (C) 2017 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 1.11.7 on 2017-12-05 16:26
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("lava_scheduler_app", "0032_add_state_health_to_testjob_and_device")
    ]

    operations = [
        migrations.RemoveField(model_name="devicestatetransition", name="created_by"),
        migrations.RemoveField(model_name="devicestatetransition", name="device"),
        migrations.RemoveField(model_name="devicestatetransition", name="job"),
        migrations.RemoveField(model_name="device", name="current_job"),
        migrations.RemoveField(model_name="device", name="health_status"),
        migrations.RemoveField(model_name="device", name="status"),
        migrations.RemoveField(model_name="notification", name="job_status_trigger"),
        migrations.RemoveField(model_name="testjob", name="requested_device"),
        migrations.RemoveField(model_name="testjob", name="status"),
        migrations.RemoveField(model_name="testjob", name="submit_token"),
        migrations.DeleteModel(name="DeviceStateTransition"),
    ]
