from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lava_results_app", "0003_auto_20150908_1522")]

    operations = [
        migrations.AlterField(
            model_name="querycondition",
            name="operator",
            field=models.CharField(
                default="exact",
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
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="querycondition",
            name="value",
            field=models.CharField(max_length=40, verbose_name="Field value"),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="testcase",
            name="suite",
            field=models.ForeignKey(
                to="lava_results_app.TestSuite", on_delete=models.CASCADE
            ),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="testdata",
            name="testjob",
            field=models.ForeignKey(
                to="lava_scheduler_app.TestJob", on_delete=models.CASCADE
            ),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="testsuite",
            name="job",
            field=models.ForeignKey(
                to="lava_scheduler_app.TestJob", on_delete=models.CASCADE
            ),
            preserve_default=True,
        ),
    ]
