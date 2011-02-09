# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'TestDeviceClass'
        db.create_table('overwatch_testdeviceclass', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=16)),
        ))
        db.send_create_signal('overwatch', ['TestDeviceClass'])

        # Adding model 'TestDevice'
        db.create_table('overwatch_testdevice', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('device_class', self.gf('django.db.models.fields.related.ForeignKey')(related_name='test_devices', to=orm['overwatch.TestDeviceClass'])),
        ))
        db.send_create_signal('overwatch', ['TestDevice'])


    def backwards(self, orm):
        
        # Deleting model 'TestDeviceClass'
        db.delete_table('overwatch_testdeviceclass')

        # Deleting model 'TestDevice'
        db.delete_table('overwatch_testdevice')


    models = {
        'overwatch.testdevice': {
            'Meta': {'object_name': 'TestDevice'},
            'device_class': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_devices'", 'to': "orm['overwatch.TestDeviceClass']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'overwatch.testdeviceclass': {
            'Meta': {'object_name': 'TestDeviceClass'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '16'})
        }
    }

    complete_apps = ['overwatch']
