# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):
    
    def forwards(self, orm):
        
        # Adding model 'SoftwarePackage'
        db.create_table('dashboard_app_softwarepackage', (
            ('version', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('dashboard_app', ['SoftwarePackage'])

        # Adding unique constraint on 'SoftwarePackage', fields ['name', 'version']
        db.create_unique('dashboard_app_softwarepackage', ['name', 'version'])

        # Adding model 'NamedAttribute'
        db.create_table('dashboard_app_namedattribute', (
            ('object_id', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=512)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=32)),
        ))
        db.send_create_signal('dashboard_app', ['NamedAttribute'])

        # Adding unique constraint on 'NamedAttribute', fields ['object_id', 'name']
        db.create_unique('dashboard_app_namedattribute', ['object_id', 'name'])

        # Adding model 'HardwareDevice'
        db.create_table('dashboard_app_hardwaredevice', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('device_type', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=256)),
        ))
        db.send_create_signal('dashboard_app', ['HardwareDevice'])

        # Adding model 'BundleStream'
        db.create_table('dashboard_app_bundlestream', (
            ('group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.Group'], null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64, blank=True)),
            ('is_anonymous', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('pathname', self.gf('django.db.models.fields.CharField')(unique=True, max_length=128)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], null=True, blank=True)),
            ('is_public', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('slug', self.gf('django.db.models.fields.CharField')(max_length=64, blank=True)),
        ))
        db.send_create_signal('dashboard_app', ['BundleStream'])

        # Adding model 'Bundle'
        db.create_table('dashboard_app_bundle', (
            ('content_sha1', self.gf('django.db.models.fields.CharField')(max_length=40, unique=True, null=True)),
            ('bundle_stream', self.gf('django.db.models.fields.related.ForeignKey')(related_name='bundles', to=orm['dashboard_app.BundleStream'])),
            ('uploaded_on', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow)),
            ('content', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True)),
            ('uploaded_by', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='uploaded_bundles', null=True, to=orm['auth.User'])),
            ('content_filename', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('is_deserialized', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('dashboard_app', ['Bundle'])

        # Adding model 'BundleDeserializationError'
        db.create_table('dashboard_app_bundledeserializationerror', (
            ('error_message', self.gf('django.db.models.fields.CharField')(max_length=1024)),
            ('bundle', self.gf('django.db.models.fields.related.ForeignKey')(related_name='deserialization_error', unique=True, primary_key=True, to=orm['dashboard_app.Bundle'])),
            ('traceback', self.gf('django.db.models.fields.TextField')(max_length=32768)),
        ))
        db.send_create_signal('dashboard_app', ['BundleDeserializationError'])

        # Adding model 'Test'
        db.create_table('dashboard_app_test', (
            ('test_id', self.gf('django.db.models.fields.CharField')(unique=True, max_length=64)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64, blank=True)),
        ))
        db.send_create_signal('dashboard_app', ['Test'])

        # Adding model 'TestCase'
        db.create_table('dashboard_app_testcase', (
            ('test', self.gf('django.db.models.fields.related.ForeignKey')(related_name='test_cases', to=orm['dashboard_app.Test'])),
            ('units', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('test_case_id', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal('dashboard_app', ['TestCase'])

        # Adding unique constraint on 'TestCase', fields ['test', 'test_case_id']
        db.create_unique('dashboard_app_testcase', ['test_id', 'test_case_id'])

        # Adding model 'SoftwareSource'
        db.create_table('dashboard_app_softwaresource', (
            ('project_name', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('branch_url', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('branch_vcs', self.gf('django.db.models.fields.CharField')(max_length=10)),
            ('commit_timestamp', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('branch_revision', self.gf('django.db.models.fields.CharField')(max_length=128)),
        ))
        db.send_create_signal('dashboard_app', ['SoftwareSource'])

        # Adding model 'TestRun'
        db.create_table('dashboard_app_testrun', (
            ('sw_image_desc', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('analyzer_assigned_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('bundle', self.gf('django.db.models.fields.related.ForeignKey')(related_name='test_runs', to=orm['dashboard_app.Bundle'])),
            ('time_check_performed', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('analyzer_assigned_uuid', self.gf('django.db.models.fields.CharField')(unique=True, max_length=36)),
            ('test', self.gf('django.db.models.fields.related.ForeignKey')(related_name='test_runs', to=orm['dashboard_app.Test'])),
            ('import_assigned_date', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('dashboard_app', ['TestRun'])

        # Adding M2M table for field sources on 'TestRun'
        db.create_table('dashboard_app_testrun_sources', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('testrun', models.ForeignKey(orm['dashboard_app.testrun'], null=False)),
            ('softwaresource', models.ForeignKey(orm['dashboard_app.softwaresource'], null=False))
        ))
        db.create_unique('dashboard_app_testrun_sources', ['testrun_id', 'softwaresource_id'])

        # Adding M2M table for field packages on 'TestRun'
        db.create_table('dashboard_app_testrun_packages', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('testrun', models.ForeignKey(orm['dashboard_app.testrun'], null=False)),
            ('softwarepackage', models.ForeignKey(orm['dashboard_app.softwarepackage'], null=False))
        ))
        db.create_unique('dashboard_app_testrun_packages', ['testrun_id', 'softwarepackage_id'])

        # Adding M2M table for field devices on 'TestRun'
        db.create_table('dashboard_app_testrun_devices', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('testrun', models.ForeignKey(orm['dashboard_app.testrun'], null=False)),
            ('hardwaredevice', models.ForeignKey(orm['dashboard_app.hardwaredevice'], null=False))
        ))
        db.create_unique('dashboard_app_testrun_devices', ['testrun_id', 'hardwaredevice_id'])

        # Adding model 'Attachment'
        db.create_table('dashboard_app_attachment', (
            ('content_filename', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('public_url', self.gf('django.db.models.fields.URLField')(max_length=512, blank=True)),
            ('object_id', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('content', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True)),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('mime_type', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('dashboard_app', ['Attachment'])

        # Adding model 'TestResult'
        db.create_table('dashboard_app_testresult', (
            ('test_run', self.gf('django.db.models.fields.related.ForeignKey')(related_name='test_results', to=orm['dashboard_app.TestRun'])),
            ('_order', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('relative_index', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('timestamp', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('microseconds', self.gf('django.db.models.fields.BigIntegerField')(null=True, blank=True)),
            ('filename', self.gf('django.db.models.fields.CharField')(max_length=1024, null=True, blank=True)),
            ('result', self.gf('django.db.models.fields.PositiveSmallIntegerField')()),
            ('measurement', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=10, blank=True)),
            ('message', self.gf('django.db.models.fields.TextField')(max_length=1024, null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('test_case', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='test_results', null=True, to=orm['dashboard_app.TestCase'])),
            ('lineno', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal('dashboard_app', ['TestResult'])
    
    
    def backwards(self, orm):
        
        # Deleting model 'SoftwarePackage'
        db.delete_table('dashboard_app_softwarepackage')

        # Removing unique constraint on 'SoftwarePackage', fields ['name', 'version']
        db.delete_unique('dashboard_app_softwarepackage', ['name', 'version'])

        # Deleting model 'NamedAttribute'
        db.delete_table('dashboard_app_namedattribute')

        # Removing unique constraint on 'NamedAttribute', fields ['object_id', 'name']
        db.delete_unique('dashboard_app_namedattribute', ['object_id', 'name'])

        # Deleting model 'HardwareDevice'
        db.delete_table('dashboard_app_hardwaredevice')

        # Deleting model 'BundleStream'
        db.delete_table('dashboard_app_bundlestream')

        # Deleting model 'Bundle'
        db.delete_table('dashboard_app_bundle')

        # Deleting model 'BundleDeserializationError'
        db.delete_table('dashboard_app_bundledeserializationerror')

        # Deleting model 'Test'
        db.delete_table('dashboard_app_test')

        # Deleting model 'TestCase'
        db.delete_table('dashboard_app_testcase')

        # Removing unique constraint on 'TestCase', fields ['test', 'test_case_id']
        db.delete_unique('dashboard_app_testcase', ['test_id', 'test_case_id'])

        # Deleting model 'SoftwareSource'
        db.delete_table('dashboard_app_softwaresource')

        # Deleting model 'TestRun'
        db.delete_table('dashboard_app_testrun')

        # Removing M2M table for field sources on 'TestRun'
        db.delete_table('dashboard_app_testrun_sources')

        # Removing M2M table for field packages on 'TestRun'
        db.delete_table('dashboard_app_testrun_packages')

        # Removing M2M table for field devices on 'TestRun'
        db.delete_table('dashboard_app_testrun_devices')

        # Deleting model 'Attachment'
        db.delete_table('dashboard_app_attachment')

        # Deleting model 'TestResult'
        db.delete_table('dashboard_app_testresult')
    
    
    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'dashboard_app.attachment': {
            'Meta': {'object_name': 'Attachment'},
            'content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True'}),
            'content_filename': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mime_type': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'public_url': ('django.db.models.fields.URLField', [], {'max_length': '512', 'blank': 'True'})
        },
        'dashboard_app.bundle': {
            'Meta': {'object_name': 'Bundle'},
            'bundle_stream': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'bundles'", 'to': "orm['dashboard_app.BundleStream']"}),
            'content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True'}),
            'content_filename': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'content_sha1': ('django.db.models.fields.CharField', [], {'max_length': '40', 'unique': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_deserialized': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'uploaded_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'uploaded_bundles'", 'null': 'True', 'to': "orm['auth.User']"}),
            'uploaded_on': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'})
        },
        'dashboard_app.bundledeserializationerror': {
            'Meta': {'object_name': 'BundleDeserializationError'},
            'bundle': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'deserialization_error'", 'unique': 'True', 'primary_key': 'True', 'to': "orm['dashboard_app.Bundle']"}),
            'error_message': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'traceback': ('django.db.models.fields.TextField', [], {'max_length': '32768'})
        },
        'dashboard_app.bundlestream': {
            'Meta': {'object_name': 'BundleStream'},
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_anonymous': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'pathname': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'dashboard_app.hardwaredevice': {
            'Meta': {'object_name': 'HardwareDevice'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'device_type': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'dashboard_app.namedattribute': {
            'Meta': {'unique_together': "(('object_id', 'name'),)", 'object_name': 'NamedAttribute'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '512'})
        },
        'dashboard_app.softwarepackage': {
            'Meta': {'unique_together': "(('name', 'version'),)", 'object_name': 'SoftwarePackage'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'dashboard_app.softwaresource': {
            'Meta': {'object_name': 'SoftwareSource'},
            'branch_revision': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'branch_url': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'branch_vcs': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'commit_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'project_name': ('django.db.models.fields.CharField', [], {'max_length': '32'})
        },
        'dashboard_app.test': {
            'Meta': {'object_name': 'Test'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'test_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'})
        },
        'dashboard_app.testcase': {
            'Meta': {'unique_together': "(('test', 'test_case_id'),)", 'object_name': 'TestCase'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_cases'", 'to': "orm['dashboard_app.Test']"}),
            'test_case_id': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'units': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        },
        'dashboard_app.testresult': {
            'Meta': {'object_name': 'TestResult'},
            '_order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lineno': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'measurement': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10', 'blank': 'True'}),
            'message': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'microseconds': ('django.db.models.fields.BigIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'relative_index': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'result': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'test_case': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'test_results'", 'null': 'True', 'to': "orm['dashboard_app.TestCase']"}),
            'test_run': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_results'", 'to': "orm['dashboard_app.TestRun']"}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'dashboard_app.testrun': {
            'Meta': {'object_name': 'TestRun'},
            'analyzer_assigned_date': ('django.db.models.fields.DateTimeField', [], {}),
            'analyzer_assigned_uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '36'}),
            'bundle': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_runs'", 'to': "orm['dashboard_app.Bundle']"}),
            'devices': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': "orm['dashboard_app.HardwareDevice']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'import_assigned_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'packages': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': "orm['dashboard_app.SoftwarePackage']"}),
            'sources': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': "orm['dashboard_app.SoftwareSource']"}),
            'sw_image_desc': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_runs'", 'to': "orm['dashboard_app.Test']"}),
            'time_check_performed': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
        }
    }
    
    complete_apps = ['dashboard_app']
