# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):
    """When faced with a field name change that does not affect the db_column,
    in this case:

    results_link = models.CharField(
        max_length=400, default=None, null=True, blank=True)

    becoming:

    _results_link = models.CharField(
        max_length=400, default=None, null=True, blank=True, db_column="results_link")

    schemamigration --auto wants to delete and re-add the field.  That's not
    at all what we want here, so this empty migration allows south to know
    about this change without actually touching the db at all.
    """


    def forwards(self, orm):
        pass

    def backwards(self, orm):
        pass

    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
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
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'dashboard_app.bundle': {
            'Meta': {'ordering': "['-uploaded_on']", 'object_name': 'Bundle'},
            '_gz_content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'db_column': "'gz_content'"}),
            '_raw_content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'db_column': "'content'"}),
            'bundle_stream': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'bundles'", 'to': "orm['dashboard_app.BundleStream']"}),
            'content_filename': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'content_sha1': ('django.db.models.fields.CharField', [], {'max_length': '40', 'unique': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_deserialized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'uploaded_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'uploaded_bundles'", 'null': 'True', 'to': "orm['auth.User']"}),
            'uploaded_on': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'})
        },
        'dashboard_app.bundlestream': {
            'Meta': {'object_name': 'BundleStream'},
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_anonymous': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'pathname': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'lava_scheduler_app.device': {
            'Meta': {'object_name': 'Device'},
            'current_job': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'+'", 'unique': 'True', 'null': 'True', 'to': "orm['lava_scheduler_app.TestJob']"}),
            'device_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lava_scheduler_app.DeviceType']"}),
            'health_status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'hostname': ('django.db.models.fields.CharField', [], {'max_length': '200', 'primary_key': 'True'}),
            'last_health_report_job': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'+'", 'unique': 'True', 'null': 'True', 'to': "orm['lava_scheduler_app.TestJob']"}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['lava_scheduler_app.Tag']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'lava_scheduler_app.devicestatetransition': {
            'Meta': {'object_name': 'DeviceStateTransition'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'created_on': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'device': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'transitions'", 'to': "orm['lava_scheduler_app.Device']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'job': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lava_scheduler_app.TestJob']", 'null': 'True', 'blank': 'True'}),
            'message': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'new_state': ('django.db.models.fields.IntegerField', [], {}),
            'old_state': ('django.db.models.fields.IntegerField', [], {})
        },
        'lava_scheduler_app.devicetype': {
            'Meta': {'object_name': 'DeviceType'},
            'health_check_job': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'primary_key': 'True'})
        },
        'lava_scheduler_app.tag': {
            'Meta': {'object_name': 'Tag'},
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50'})
        },
        'lava_scheduler_app.testjob': {
            'Meta': {'object_name': 'TestJob'},
            '_results_bundle': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['dashboard_app.Bundle']", 'null': 'True', 'db_column': "'results_bundle_id'", 'blank': 'True'}),
            '_results_link': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '400', 'null': 'True', 'db_column': "'results_link'", 'blank': 'True'}),
            'actual_device': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'+'", 'null': 'True', 'blank': 'True', 'to': "orm['lava_scheduler_app.Device']"}),
            'definition': ('django.db.models.fields.TextField', [], {}),
            'description': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.Group']", 'null': 'True', 'blank': 'True'}),
            'health_check': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'log_file': ('django.db.models.fields.files.FileField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'requested_device': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'+'", 'null': 'True', 'blank': 'True', 'to': "orm['lava_scheduler_app.Device']"}),
            'requested_device_type': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'+'", 'null': 'True', 'blank': 'True', 'to': "orm['lava_scheduler_app.DeviceType']"}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'submit_time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'submit_token': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['linaro_django_xmlrpc.AuthToken']", 'null': 'True', 'blank': 'True'}),
            'submitter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': "orm['auth.User']"}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['lava_scheduler_app.Tag']", 'symmetrical': 'False', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'linaro_django_xmlrpc.authtoken': {
            'Meta': {'object_name': 'AuthToken'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_used_on': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'secret': ('django.db.models.fields.CharField', [], {'default': "'dous3jo4hqd6e52q3s52t90dt8uebg4igr60u4a70x052l8wob80ha0ppilxjcm75ymkhrlgpyoppnccn1riu9ckp20wu9jtyptd037few649pglrwom1gntkjpzib52'", 'unique': 'True', 'max_length': '128'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'auth_tokens'", 'to': "orm['auth.User']"})
        }
    }

    complete_apps = ['lava_scheduler_app']
