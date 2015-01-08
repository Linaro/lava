# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0008_imagechartfilter_is_all_tests_included'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testresult',
            name='measurement',
            field=models.CharField(blank=True, max_length=512, help_text="Arbitrary value that was measured as a part of this test.", null=True, verbose_name="Measurement"),
        ),
    ]
