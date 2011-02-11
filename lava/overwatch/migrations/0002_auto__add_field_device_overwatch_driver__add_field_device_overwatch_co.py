# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'Device.overwatch_driver'
        db.add_column('overwatch_device', 'overwatch_driver', self.gf('django.db.models.fields.CharField')(default='dummy', max_length=255), keep_default=False)

        # Adding field 'Device.overwatch_config'
        db.add_column('overwatch_device', 'overwatch_config', self.gf('django.db.models.fields.TextField')(default='', max_length=65535, blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'Device.overwatch_driver'
        db.delete_column('overwatch_device', 'overwatch_driver')

        # Deleting field 'Device.overwatch_config'
        db.delete_column('overwatch_device', 'overwatch_config')


    models = {
        'overwatch.device': {
            'Meta': {'object_name': 'Device'},
            'device_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'devices'", 'to': "orm['overwatch.DeviceType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'overwatch_config': ('django.db.models.fields.TextField', [], {'default': "''", 'max_length': '65535', 'blank': 'True'}),
            'overwatch_driver': ('django.db.models.fields.CharField', [], {'default': "'dummy'", 'max_length': '255'})
        },
        'overwatch.devicetype': {
            'Meta': {'object_name': 'DeviceType'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        }
    }

    complete_apps = ['overwatch']
