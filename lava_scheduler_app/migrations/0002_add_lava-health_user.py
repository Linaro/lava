import uuid

from django.db import IntegrityError, migrations, transaction
from django.utils import timezone


def forwards_func(apps, schema_editor):
    User = apps.get_model("auth", "User")
    db_alias = schema_editor.connection.alias
    now = timezone.now()
    password = uuid.uuid4().hex
    try:
        with transaction.atomic():
            new_user = User.objects.using(db_alias).create(
                username="lava-health",
                email="lava@lava.invalid",
                is_staff=False,
                is_active=True,
                is_superuser=False,
                last_login=now,
                date_joined=now,
            )
            new_user.password = password
            new_user.save()
    except IntegrityError:
        new_user = User.objects.using(db_alias).get(username="lava-health")
        if new_user.password == "!":
            new_user.password = password
            new_user.save()
            print("lava-health user exists, password updated ...")
        else:
            print("lava-health user exists, leaving it intact ...")


def backwards_func(apps, schema_editor):
    User = apps.get_model("auth", "User")
    db_alias = schema_editor.connection.alias
    lava_health = User.objects.using(db_alias).filter(username="lava-health")
    lava_health.delete()


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0001_initial")]

    operations = [migrations.RunPython(forwards_func, backwards_func)]
