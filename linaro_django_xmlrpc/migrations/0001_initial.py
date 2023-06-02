from django.conf import settings
from django.db import migrations, models

import linaro_django_xmlrpc.models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "__first__"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuthToken",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                (
                    "secret",
                    models.CharField(
                        default=linaro_django_xmlrpc.models._make_secret,
                        help_text="Secret randomly generated text that grants user access instead of their regular password",
                        unique=True,
                        max_length=128,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        default="",
                        help_text="Arbitrary text that helps the user to associate tokens with their intended purpose",
                        blank=True,
                    ),
                ),
                (
                    "created_on",
                    models.DateTimeField(
                        help_text="Time and date when the token was created",
                        auto_now=True,
                    ),
                ),
                (
                    "last_used_on",
                    models.DateTimeField(
                        help_text="Time and date when the token was last used",
                        null=True,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        related_name="auth_tokens",
                        to=settings.AUTH_USER_MODEL,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
        )
    ]
