# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'DeviceClass'
        db.create_table('overwatch_deviceclass', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=16)),
        ))
        db.send_create_signal('overwatch', ['DeviceClass'])

        # Adding model 'device'
        db.create_table('overwatch_device', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('device_class', self.gf('django.db.models.fields.related.ForeignKey')(related_name='devices', to=orm['overwatch.DeviceClass'])),
        ))
        db.send_create_signal('overwatch', ['device'])


    def backwards(self, orm):
        
        # Deleting model 'deviceClass'
        db.delete_table('overwatch_deviceclass')

        # Deleting model 'device'
        db.delete_table('overwatch_device')


    models = {
        'overwatch.device': {
            'Meta': {'object_name': 'Device'},
            'device_class': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'devices'", 'to': "orm['overwatch.DeviceClass']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'overwatch.deviceclass': {
            'Meta': {'object_name': 'DeviceClass'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '16'})
        }
    }

    complete_apps = ['overwatch']
