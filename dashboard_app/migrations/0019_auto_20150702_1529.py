# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0018_imagereport_group'),
    ]

    operations = [
        migrations.RunSQL(
            sql="SET LOCAL statement_timeout to 10000000;",
            reverse_sql="SET LOCAL statement_timeout to 30000;"
        ),
        migrations.AlterUniqueTogether(
            name='namedattribute',
            unique_together=set([('object_id', 'name', 'content_type')]),
        ),
    ]
