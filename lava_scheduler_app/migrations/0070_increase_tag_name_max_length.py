# SPDX-License-Identifier: GPL-2.0-or-later

# Increase Tag.name max_length from the SlugField default of 50 to 100 so
# long, descriptive device tags (e.g. "usb-hub-p1_kingston-datatraveler-
# kyson-128gb-usb-32") don't fail with "value too long for type character
# varying(50)".

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0069_testjob_metadata_gin_index")]

    operations = [
        migrations.AlterField(
            model_name="tag",
            name="name",
            field=models.SlugField(max_length=100, unique=True),
        )
    ]
