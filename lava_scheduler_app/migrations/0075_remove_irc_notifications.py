# SPDX-License-Identifier: GPL-2.0-or-later

# IRC notifications have been removed: delete the recipients that were
# waiting for an IRC message and drop the IRC specific fields.

from django.db import migrations, models


def delete_irc_recipients(apps, schema_editor):
    NotificationRecipient = apps.get_model(
        "lava_scheduler_app", "NotificationRecipient"
    )
    # 1 was NotificationRecipient.IRC
    NotificationRecipient.objects.filter(method=1).delete()


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0074_testjob_add_missing_permissions")]

    operations = [
        migrations.RunPython(
            delete_irc_recipients,
            migrations.RunPython.noop,
            elidable=True,
        ),
        migrations.RemoveField(model_name="extendeduser", name="irc_handle"),
        migrations.RemoveField(model_name="extendeduser", name="irc_server"),
        migrations.RemoveField(model_name="notificationrecipient", name="irc_handle"),
        migrations.RemoveField(model_name="notificationrecipient", name="irc_server"),
        migrations.AlterField(
            model_name="notificationrecipient",
            name="method",
            field=models.IntegerField(
                choices=[(0, "email")], default=0, verbose_name="Method"
            ),
        ),
    ]
