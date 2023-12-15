# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0004_add_pipeline_marks")]

    operations = [
        migrations.CreateModel(
            name="DeviceDictionaryTable",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("kee", models.CharField(max_length=255)),
                ("value", models.TextField()),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="PipelineStore",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("kee", models.CharField(max_length=255)),
                ("value", models.TextField()),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.AlterField(
            model_name="device",
            name="is_pipeline",
            field=models.BooleanField(default=False, verbose_name="Pipeline device?"),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="testjob",
            name="is_pipeline",
            field=models.BooleanField(
                default=False, verbose_name="Pipeline job?", editable=False
            ),
            preserve_default=True,
        ),
    ]
