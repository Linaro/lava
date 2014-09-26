# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dashboard_app', '0002_auto_20140917_1935'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImageChartTestAttributeUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_visible', models.BooleanField(default=True, verbose_name=b'Visible')),
                ('image_chart_test_attribute', models.ForeignKey(to='dashboard_app.ImageChartTestAttribute')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='imagecharttestattributeuser',
            unique_together=set([('image_chart_test_attribute', 'user')]),
        ),
        migrations.AlterField(
            model_name='imagereportchart',
            name='chart_type',
            field=models.CharField(default=b'pass/fail', max_length=20, verbose_name=b'Chart type', choices=[(b'pass/fail', b'Pass/Fail'), (b'measurement', b'Measurement'), (b'attributes', b'Attributes')]),
        ),
    ]
