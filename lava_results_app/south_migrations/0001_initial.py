# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    depends_on = (
        ("lava_scheduler_app", "0050_auto__add_field_devicetype_description"),
    )

    def forwards(self, orm):
        # Adding model 'TestSuite'
        db.create_table(u'lava_results_app_testsuite', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('job', self.gf('django.db.models.fields.related.ForeignKey')(related_name='test_suites', to=orm['lava_scheduler_app.TestJob'])),
            ('name', self.gf('django.db.models.fields.CharField')(default=None, max_length=200, null=True, blank=True)),
        ))
        db.send_create_signal(u'lava_results_app', ['TestSuite'])

        # Adding model 'TestSet'
        db.create_table(u'lava_results_app_testset', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(default=None, max_length=200, null=True, blank=True)),
            ('suite', self.gf('django.db.models.fields.related.ForeignKey')(related_name='test_sets', to=orm['lava_results_app.TestSuite'])),
        ))
        db.send_create_signal(u'lava_results_app', ['TestSet'])

        # Adding model 'TestCase'
        db.create_table(u'lava_results_app_testcase', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('units', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('result', self.gf('django.db.models.fields.PositiveSmallIntegerField')()),
            ('measurement', self.gf('django.db.models.fields.CharField')(max_length=512, null=True, blank=True)),
            ('metadata', self.gf('django.db.models.fields.CharField')(max_length=1024, null=True, blank=True)),
            ('suite', self.gf('django.db.models.fields.related.ForeignKey')(related_name='test_cases', to=orm['lava_results_app.TestSuite'])),
            ('test_set', self.gf('django.db.models.fields.related.ForeignKey')(default=None, related_name='test_cases', null=True, blank=True, to=orm['lava_results_app.TestSet'])),
            ('logged', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal(u'lava_results_app', ['TestCase'])

        # Adding model 'MetaType'
        db.create_table(u'lava_results_app_metatype', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('metatype', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal(u'lava_results_app', ['MetaType'])

        # Adding model 'TestData'
        db.create_table(u'lava_results_app_testdata', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('testjob', self.gf('django.db.models.fields.related.ForeignKey')(related_name='test_data', to=orm['lava_scheduler_app.TestJob'])),
        ))
        db.send_create_signal(u'lava_results_app', ['TestData'])

        # Adding model 'ActionData'
        db.create_table(u'lava_results_app_actiondata', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('action_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('action_level', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('action_summary', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('action_description', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('meta_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='actionlevels', to=orm['lava_results_app.MetaType'])),
            ('testdata', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='actionlevels', null=True, to=orm['lava_results_app.TestData'])),
            ('yaml_line', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
            ('description_line', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
            ('log_section', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('duration', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=8, decimal_places=2, blank=True)),
            ('timeout', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
            ('testcase', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='actionlevels', null=True, to=orm['lava_results_app.TestCase'])),
            ('count', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
            ('max_retries', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'lava_results_app', ['ActionData'])

    def backwards(self, orm):
        # Deleting model 'TestSuite'
        db.delete_table(u'lava_results_app_testsuite')

        # Deleting model 'TestSet'
        db.delete_table(u'lava_results_app_testset')

        # Deleting model 'TestCase'
        db.delete_table(u'lava_results_app_testcase')

        # Deleting model 'MetaType'
        db.delete_table(u'lava_results_app_metatype')

        # Deleting model 'TestData'
        db.delete_table(u'lava_results_app_testdata')

        # Deleting model 'ActionData'
        db.delete_table(u'lava_results_app_actiondata')

    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'dashboard_app.bundle': {
            'Meta': {'ordering': "['-uploaded_on']", 'object_name': 'Bundle'},
            '_gz_content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'db_column': "'gz_content'"}),
            '_raw_content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'db_column': "'content'"}),
            'bundle_stream': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'bundles'", 'to': u"orm['dashboard_app.BundleStream']"}),
            'content_filename': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'content_sha1': ('django.db.models.fields.CharField', [], {'max_length': '40', 'unique': 'True', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_deserialized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'uploaded_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'uploaded_bundles'", 'null': 'True', 'to': u"orm['auth.User']"}),
            'uploaded_on': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'})
        },
        u'dashboard_app.bundlestream': {
            'Meta': {'object_name': 'BundleStream'},
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.Group']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_anonymous': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'pathname': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        u'lava_results_app.actiondata': {
            'Meta': {'object_name': 'ActionData'},
            'action_description': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'action_level': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'action_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'action_summary': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'count': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'description_line': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'duration': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '8', 'decimal_places': '2', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'log_section': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'max_retries': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'meta_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'actionlevels'", 'to': u"orm['lava_results_app.MetaType']"}),
            'testcase': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'actionlevels'", 'null': 'True', 'to': u"orm['lava_results_app.TestCase']"}),
            'testdata': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'actionlevels'", 'null': 'True', 'to': u"orm['lava_results_app.TestData']"}),
            'timeout': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'yaml_line': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        u'lava_results_app.metatype': {
            'Meta': {'object_name': 'MetaType'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'metatype': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '32'})
        },
        u'lava_results_app.testcase': {
            'Meta': {'object_name': 'TestCase'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'logged': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'measurement': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'metadata': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'result': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'suite': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_cases'", 'to': u"orm['lava_results_app.TestSuite']"}),
            'test_set': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'test_cases'", 'null': 'True', 'blank': 'True', 'to': u"orm['lava_results_app.TestSet']"}),
            'units': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'lava_results_app.testdata': {
            'Meta': {'object_name': 'TestData'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'testjob': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_data'", 'to': u"orm['lava_scheduler_app.TestJob']"})
        },
        u'lava_results_app.testset': {
            'Meta': {'object_name': 'TestSet'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'suite': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_sets'", 'to': u"orm['lava_results_app.TestSuite']"})
        },
        u'lava_results_app.testsuite': {
            'Meta': {'object_name': 'TestSuite'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'job': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_suites'", 'to': u"orm['lava_scheduler_app.TestJob']"}),
            'name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'lava_scheduler_app.device': {
            'Meta': {'object_name': 'Device'},
            'current_job': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': u"orm['lava_scheduler_app.TestJob']", 'blank': 'True', 'unique': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'device_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['lava_scheduler_app.DeviceType']"}),
            'device_version': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.Group']", 'null': 'True', 'blank': 'True'}),
            'health_status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'hostname': ('django.db.models.fields.CharField', [], {'max_length': '200', 'primary_key': 'True'}),
            'is_pipeline': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_health_report_job': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': u"orm['lava_scheduler_app.TestJob']", 'blank': 'True', 'unique': 'True'}),
            'physical_group': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'physical-group'", 'null': 'True', 'blank': 'True', 'to': u"orm['auth.Group']"}),
            'physical_owner': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'physical-owner'", 'null': 'True', 'blank': 'True', 'to': u"orm['auth.User']"}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['lava_scheduler_app.Tag']", 'symmetrical': 'False', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'worker_host': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': u"orm['lava_scheduler_app.Worker']", 'null': 'True', 'blank': 'True'})
        },
        u'lava_scheduler_app.devicetype': {
            'Meta': {'object_name': 'DeviceType'},
            'display': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'health_check_job': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'primary_key': 'True'}),
            'owners_only': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'lava_scheduler_app.jobfailuretag': {
            'Meta': {'object_name': 'JobFailureTag'},
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'})
        },
        u'lava_scheduler_app.tag': {
            'Meta': {'object_name': 'Tag'},
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50'})
        },
        u'lava_scheduler_app.testjob': {
            'Meta': {'object_name': 'TestJob'},
            '_results_bundle': ('django.db.models.fields.related.OneToOneField', [], {'null': 'True', 'db_column': "'results_bundle_id'", 'on_delete': 'models.SET_NULL', 'to': u"orm['dashboard_app.Bundle']", 'blank': 'True', 'unique': 'True'}),
            '_results_link': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '400', 'null': 'True', 'db_column': "'results_link'", 'blank': 'True'}),
            'actual_device': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'+'", 'null': 'True', 'blank': 'True', 'to': u"orm['lava_scheduler_app.Device']"}),
            'admin_notifications': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'definition': ('django.db.models.fields.TextField', [], {}),
            'description': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'failure_comment': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'failure_tags': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'failure_tags'", 'blank': 'True', 'to': u"orm['lava_scheduler_app.JobFailureTag']"}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.Group']", 'null': 'True', 'blank': 'True'}),
            'health_check': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_pipeline': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'log_file': ('django.db.models.fields.files.FileField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'multinode_definition': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'original_definition': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'priority': ('django.db.models.fields.IntegerField', [], {'default': '50'}),
            'requested_device': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'+'", 'null': 'True', 'blank': 'True', 'to': u"orm['lava_scheduler_app.Device']"}),
            'requested_device_type': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'+'", 'null': 'True', 'blank': 'True', 'to': u"orm['lava_scheduler_app.DeviceType']"}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sub_id': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'submit_time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'submit_token': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['linaro_django_xmlrpc.AuthToken']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'submitter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': u"orm['auth.User']"}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['lava_scheduler_app.Tag']", 'symmetrical': 'False', 'blank': 'True'}),
            'target_group': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'vm_group': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'vmgroup_definition': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'lava_scheduler_app.worker': {
            'Meta': {'object_name': 'Worker'},
            'arch': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'display': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hardware_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'primary_key': 'True'}),
            'ip_address': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'is_master': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_heartbeat': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'last_master_scheduler_tick': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'platform': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'rpc2_url': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'software_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'uptime': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'linaro_django_xmlrpc.authtoken': {
            'Meta': {'object_name': 'AuthToken'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_used_on': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'secret': ('django.db.models.fields.CharField', [], {'default': "'mj8ca3g5cdbruddo6ns7e7u73uqkk51p4spae3hx3p3shgdnwjwgqts2mfj8dxsx11zq2pw0hyzf0qgsfj0bjtq0yxp1atsbsmjm5a4c452j0k8q6metzr4twtymta7u'", 'unique': 'True', 'max_length': '128'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'auth_tokens'", 'to': u"orm['auth.User']"})
        }
    }

    complete_apps = ['lava_results_app']
