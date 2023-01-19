# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-08 16:00
from django.db import migrations, models

import lava_scheduler_app.models


class Migration(migrations.Migration):

    dependencies = [("lava_scheduler_app", "0011_remove_testjob_log_file")]

    operations = [
        migrations.AddField(
            model_name="devicetype",
            name="health_denominator",
            field=models.IntegerField(
                choices=[(0, "hours"), (1, "jobs")],
                default=0,
                help_text="Choose to submit a health check every N hours or every N jobs. Balance against the duration ofa health check job and the average job duration.",
                verbose_name="Initiate health checks by hours or by jobs.",
            ),
        ),
        migrations.AddField(
            model_name="devicetype",
            name="health_frequency",
            field=models.IntegerField(
                default=24, verbose_name="How often to run health checks"
            ),
        ),
        migrations.AlterField(
            model_name="devicetype",
            name="health_check_job",
            field=models.TextField(
                blank=True,
                default=None,
                null=True,
                validators=[lava_scheduler_app.dbutils.validate_job],
            ),
        ),
    ]
