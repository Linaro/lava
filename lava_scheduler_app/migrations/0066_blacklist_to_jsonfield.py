# SPDX-License-Identifier: GPL-2.0-or-later
from django.db import migrations

TABLE = "lava_scheduler_app_notification"
COLUMN = "blacklist"


def array_to_jsonb(apps, schema_editor):
    # Existing PostgreSQL installs created this column as a varchar[] ArrayField
    # (migration 0021). Convert it in place to jsonb, preserving the data.
    # Fresh installs already have jsonb (or, on SQLite, a text column) so this
    # is a no-op for them.
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s",
            [TABLE, COLUMN],
        )
        row = cursor.fetchone()
    if row and row[0] == "ARRAY":
        schema_editor.execute(
            f"ALTER TABLE {TABLE} "
            f"ALTER COLUMN {COLUMN} TYPE jsonb USING to_jsonb({COLUMN})"
        )


def jsonb_to_array(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    schema_editor.execute(
        f"ALTER TABLE {TABLE} "
        f"ALTER COLUMN {COLUMN} TYPE varchar(100)[] "
        f"USING translate({COLUMN}::text, '[]', '{{}}')::varchar(100)[]"
    )


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0065_alter_devicetype_health_frequency_default")]

    operations = [migrations.RunPython(array_to_jsonb, jsonb_to_array)]
