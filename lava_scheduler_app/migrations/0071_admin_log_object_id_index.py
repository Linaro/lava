# SPDX-License-Identifier: GPL-2.0-or-later

from django.db import migrations

INDEX_NAME = "django_admin_log_object_id_action_time_idx"


def add_index(apps, schema_editor):
    concurrently = (
        "CONCURRENTLY " if schema_editor.connection.vendor == "postgresql" else ""
    )
    schema_editor.execute(
        f"CREATE INDEX {concurrently}{INDEX_NAME} "
        "ON django_admin_log (object_id, action_time DESC)"
    )


def drop_index(apps, schema_editor):
    concurrently = (
        "CONCURRENTLY " if schema_editor.connection.vendor == "postgresql" else ""
    )
    schema_editor.execute(f"DROP INDEX {concurrently}IF EXISTS {INDEX_NAME}")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("lava_scheduler_app", "0070_increase_tag_name_max_length"),
        ("admin", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_index, drop_index),
    ]
