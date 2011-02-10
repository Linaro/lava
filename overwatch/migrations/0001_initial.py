# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'DeviceType'
        db.create_table('overwatch_devicetype', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('overwatch', ['DeviceType'])

        # Adding model 'Device'
        db.create_table('overwatch_device', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('device_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='devices', to=orm['overwatch.DeviceType'])),
        ))
        db.send_create_signal('overwatch', ['Device'])


    def backwards(self, orm):
        
        # Deleting model 'DeviceType'
        db.delete_table('overwatch_devicetype')

        # Deleting model 'Device'
        db.delete_table('overwatch_device')


    models = {
        'overwatch.device': {
            'Meta': {'object_name': 'Device'},
            'device_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'devices'", 'to': "orm['overwatch.DeviceType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'overwatch.devicetype': {
            'Meta': {'object_name': 'DeviceType'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        }
    }

    complete_apps = ['overwatch']
