# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('google_analytics', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='analytic',
            name='site',
            field=models.OneToOneField(to='sites.Site'),
        ),
    ]
