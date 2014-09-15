# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    depends_on = (
        ("dashboard_app", "0027_auto__del_testingeffort"),
    )

    def forwards(self, orm):
        # Deleting model 'ProjectFormerIdentifier'
        db.delete_table('lava_projects_projectformeridentifier')

        # Deleting model 'Project'
        db.delete_table('lava_projects_project')

    def backwards(self, orm):
        # Adding model 'ProjectFormerIdentifier'
        db.create_table('lava_projects_projectformeridentifier', (
            ('renamed_by', self.gf('django.db.models.fields.related.ForeignKey')(related_name='project_former_identifiers_created', to=orm['auth.User'])),
            ('renamed_on', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('project', self.gf('django.db.models.fields.related.ForeignKey')(related_name='former_identifiers', to=orm['lava_projects.Project'])),
            ('former_identifier', self.gf('django.db.models.fields.SlugField')(max_length=100, unique=True, db_index=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('lava_projects', ['ProjectFormerIdentifier'])

        # Adding model 'Project'
        db.create_table('lava_projects_project', (
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('registered_by', self.gf('django.db.models.fields.related.ForeignKey')(related_name='projects', to=orm['auth.User'])),
            ('is_aggregate', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], null=True, blank=True)),
            ('is_public', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.Group'], null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('registered_on', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('identifier', self.gf('django.db.models.fields.SlugField')(max_length=100, unique=True, db_index=True)),
        ))
        db.send_create_signal('lava_projects', ['Project'])

    models = {

    }

    complete_apps = ['lava_projects']
