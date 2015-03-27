# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


def remove_stale_content_types(apps, schema_editor):
    # Remove known stale objects from django_content_type table.
    ContentType = apps.get_model("contenttypes", "ContentType")
    models = {
        ("auth", "message"),
        ("dashboard_app", "launchpadbug"),
        ("dashboard_app", "imagecharttestrun"),
        ("dashboard_app", "testingeffort"),
        ("dashboard_app", "imageattribute")
    }
    for model in models:
        try:
            ContentType.objects.get(app_label=model[0],
                                    model=model[1]).delete()
        except ContentType.DoesNotExist:
            pass


def reverse_func(apps, schema_editor):
    # Content types are automatically added by django.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0014_auto_20150212_0604'),
    ]

    operations = [
        migrations.RunPython(
            remove_stale_content_types,
            reverse_func
        ),
    ]
