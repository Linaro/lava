import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_results_app", "0004_auto_20150925_0002")]

    operations = [
        migrations.AlterModelOptions(
            name="query",
            options={"verbose_name": "query", "verbose_name_plural": "queries"},
        ),
        migrations.AddField(
            model_name="query",
            name="is_archived",
            field=models.BooleanField(default=False, verbose_name="Archived"),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="query",
            name="group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                default=None,
                blank=True,
                to="auth.Group",
                null=True,
            ),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="query",
            name="query_group",
            field=models.ForeignKey(
                default=None,
                blank=True,
                to="lava_results_app.QueryGroup",
                null=True,
                on_delete=models.CASCADE,
            ),
            preserve_default=True,
        ),
    ]
