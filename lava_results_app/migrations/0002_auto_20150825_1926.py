import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contenttypes", "0001_initial"),
        ("lava_results_app", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Query",
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
                    "name",
                    models.SlugField(
                        help_text="The <b>name</b> of a query is used to refer to it in the web UI.",
                        max_length=1024,
                    ),
                ),
                ("description", models.TextField(null=True, blank=True)),
                (
                    "is_published",
                    models.BooleanField(default=False, verbose_name="Published"),
                ),
                (
                    "group_by_attribute",
                    models.CharField(
                        max_length=20,
                        null=True,
                        verbose_name="group by attribute",
                        blank=True,
                    ),
                ),
                (
                    "target_goal",
                    models.DecimalField(
                        null=True,
                        verbose_name="Target goal",
                        max_digits=10,
                        decimal_places=5,
                        blank=True,
                    ),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        verbose_name="Query object set",
                        to="contenttypes.ContentType",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        default=None,
                        to="auth.Group",
                        null=True,
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="QueryCondition",
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
                ("field", models.CharField(max_length=50, verbose_name="Field name")),
                (
                    "operator",
                    models.CharField(
                        max_length=20,
                        verbose_name="Operator",
                        choices=[
                            ("exact", "Exact match"),
                            ("iexact", "Case-insensitive match"),
                            ("icontains", "Contains"),
                            ("gt", "Greater than"),
                            ("lt", "Less than"),
                        ],
                    ),
                ),
                ("value", models.CharField(max_length=50, verbose_name="Field value")),
                (
                    "query",
                    models.ForeignKey(
                        to="lava_results_app.Query", on_delete=models.CASCADE
                    ),
                ),
                (
                    "table",
                    models.ForeignKey(
                        verbose_name="Condition model",
                        to="contenttypes.ContentType",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="QueryGroup",
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
                ("name", models.SlugField(unique=True, max_length=1024)),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name="query",
            name="query_group",
            field=models.ForeignKey(
                default=None,
                to="lava_results_app.QueryGroup",
                null=True,
                on_delete=models.CASCADE,
            ),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name="query", unique_together={("owner", "name")}
        ),
    ]
