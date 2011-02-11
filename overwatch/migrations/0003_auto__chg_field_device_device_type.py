# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Changing field 'Device.device_type'
        db.alter_column('overwatch_device', 'device_type_id', self.gf('django.db.models.fields.related.ForeignKey')(null=True, to=orm['overwatch.DeviceType']))


    def backwards(self, orm):
        
        # User chose to not deal with backwards NULL issues for 'Device.device_type'
        raise RuntimeError("Cannot reverse this migration. 'Device.device_type' and its values cannot be restored.")


    models = {
        'overwatch.device': {
            'Meta': {'object_name': 'Device'},
            'device_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'devices'", 'null': 'True', 'to': "orm['overwatch.DeviceType']"}),
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
