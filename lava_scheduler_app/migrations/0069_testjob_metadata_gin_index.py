# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: GPL-2.0-or-later
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations


class AddIndexConcurrentlyIfSupported(AddIndexConcurrently):
    """
    CREATE INDEX CONCURRENTLY is specific to PostgreSQL. Other backends, used
    by some development setups, create the index the usual way. They also
    ignore the GIN index type and create a regular index instead.
    """

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
    # Building the GIN index takes a long time on instances with a large
    # lava_scheduler_app_testjob table. Build it concurrently so that job
    # submission is not blocked while the migration runs. CREATE INDEX
    # CONCURRENTLY cannot run inside a transaction.
    atomic = False

    dependencies = [
        ("lava_scheduler_app", "0068_testjob_metadata"),
    ]

    operations = [
        AddIndexConcurrentlyIfSupported(
            model_name="testjob",
            index=GinIndex(fields=["metadata"], name="testjob_metadata_gin_index"),
        ),
    ]
