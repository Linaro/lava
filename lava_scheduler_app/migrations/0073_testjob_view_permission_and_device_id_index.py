# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class AddIndexConcurrentlyIfSupported(AddIndexConcurrently):
    """Same helper as in 0069: non-PostgreSQL dev backends fall back to a
    regular CREATE INDEX."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != "postgresql":
            return migrations.AddIndex.database_forwards(
                self, app_label, schema_editor, from_state, to_state
            )
        return super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != "postgresql":
            return migrations.AddIndex.database_backwards(
                self, app_label, schema_editor, from_state, to_state
            )
        return super().database_backwards(
            app_label, schema_editor, from_state, to_state
        )


class Migration(migrations.Migration):
    # The index is built concurrently so that job submission is not blocked
    # on instances with a large lava_scheduler_app_testjob table. CREATE INDEX
    # CONCURRENTLY cannot run inside a transaction. If the build fails it
    # leaves an INVALID index behind; drop it with
    # "DROP INDEX CONCURRENTLY device_jobs_by_id_index" before re-running
    # migrate. Django's post-migrate hook creates the view_testjob row from
    # the Meta.permissions declared below.
    atomic = False

    dependencies = [
        ("lava_scheduler_app", "0072_testjob_pool_pattern"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="testjob",
            options={
                "default_permissions": ("change", "delete"),
                "permissions": (("view_testjob", "Can view test job"),),
            },
        ),
        AddIndexConcurrentlyIfSupported(
            model_name="testjob",
            index=models.Index(
                fields=["actual_device", "-id"], name="device_jobs_by_id_index"
            ),
        ),
    ]
