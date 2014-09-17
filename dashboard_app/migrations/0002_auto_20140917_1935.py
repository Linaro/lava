# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bundle',
            name='is_deserialized',
            field=models.BooleanField(default=False, help_text='Set when document has been analyzed and loaded into the database', verbose_name='Is deserialized', editable=False),
        ),
        migrations.AlterField(
            model_name='bundlestream',
            name='is_anonymous',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='testrun',
            name='time_check_performed',
            field=models.BooleanField(default=False, help_text="Indicator on wether timestamps in the log file (and any data derived from them) should be trusted.<br/>Many pre-production or development devices do not have a battery-powered RTC and it's not common for development images not to synchronize time with internet time servers.<br/>This field allows us to track tests results that <em>certainly</em> have correct time if we ever end up with lots of tests results from 1972", verbose_name='Time check performed'),
        ),
    ]
