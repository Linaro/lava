# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-11-27 10:10
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


def forwards_func(apps, schema_editor):
    # Delete testdata records other then the first one in testjob objects.
    TestJob = apps.get_model("lava_scheduler_app", "TestJob")
    db_alias = schema_editor.connection.alias

    for job in (
        TestJob.objects.using(db_alias)
        .annotate(num_testdata=models.Count("testdata"))
        .filter(num_testdata__gt=1)
    ):
        first_testdata = job.testdata_set.first()
        job.testdata_set.exclude(pk=first_testdata.pk).delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [("lava_results_app", "0016_add_testcase_start_end_tc")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards_func, noop, atomic=True)
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="testdata",
                    name="testjob",
                    field=models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="lava_scheduler_app.TestJob",
                    ),
                )
            ],
        )
    ]
