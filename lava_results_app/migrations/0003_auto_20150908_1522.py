from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_results_app", "0002_auto_20150825_1926")]

    operations = [
        migrations.AddField(
            model_name="query",
            name="is_changed",
            field=models.BooleanField(default=False, verbose_name="Live query"),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="query",
            name="is_live",
            field=models.BooleanField(default=False, verbose_name="Live query"),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="query",
            name="is_updating",
            field=models.BooleanField(default=False, verbose_name="Live query"),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="query",
            name="last_updated",
            field=models.DateTimeField(null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="querycondition",
            name="value",
            field=models.CharField(max_length=20, verbose_name="Field value"),
            preserve_default=True,
        ),
    ]
