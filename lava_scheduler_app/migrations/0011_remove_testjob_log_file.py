# Copyright (C) 2016 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 1.9.1 on 2016-01-11 12:47
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0010_auto_20151103_1136")]

    operations = [migrations.RemoveField(model_name="testjob", name="log_file")]
