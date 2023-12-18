# Copyright (C) 2016 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# Generated by Django 1.9.6 on 2016-05-20 13:18
import django.db.models.deletion
from django.db import migrations, models

from lava_results_app.models import QueryMaterializedView


def remove_views(apps, schema_editor):
    # Remove materialized views for all queries of content type TestCase.
    Query = apps.get_model("lava_results_app", "Query")
    db_alias = schema_editor.connection.alias
    for query in Query.objects.using(db_alias).filter(content_type__model="testcase"):
        QueryMaterializedView.drop(query.id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("lava_results_app", "0010_auto_20160504_0814")]

    operations = [
        migrations.RunPython(remove_views, noop),
        migrations.CreateModel(
            name="NamedTestAttribute",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.TextField()),
                ("value", models.TextField()),
                ("object_id", models.PositiveIntegerField()),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.ContentType",
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="metatype", name="name", field=models.CharField(max_length=256)
        ),
        migrations.AlterField(
            model_name="testcase",
            name="metadata",
            field=models.CharField(
                blank=True,
                help_text="Metadata collected by the pipeline action, stored as YAML.",
                max_length=4096,
                null=True,
                verbose_name="Action meta data as a YAML string",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="namedtestattribute",
            unique_together={("object_id", "name", "content_type")},
        ),
        migrations.RunPython(noop, remove_views),
    ]
