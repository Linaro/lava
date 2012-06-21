# -*- coding: utf-8 -*-
import datetime
import sys
from south.db import db
from south.v2 import DataMigration
from django.db import models


class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        count = 0
        query = orm['lava_scheduler_app.TestJob'].objects.filter(
            results_link__isnull=False)
        print query.count()
        for job in query.all():
            count += 1
            if count % 100 == 0:
                sys.stdout.write('.')
                sys.stdout.flush()
            sha1 = job.results_link.strip('/').split('/')[-1]
            try:
                bundle = orm['dashboard_app.Bundle'].objects.get(content_sha1=sha1)
            except orm['dashboard_app.Bundle'].DoesNotExist:
                continue
            job._results_bundle = bundle
            job.save()

    def backwards(self, orm):
        "Write your backwards methods here."
        orm['lava_scheduler_app.TestJob'].objects.update(_results_bundle=None)

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
        'dashboard_app.bundledeserializationerror': {
            'Meta': {'object_name': 'BundleDeserializationError'},
            'bundle': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'deserialization_error'", 'unique': 'True', 'primary_key': 'True', 'to': "orm['dashboard_app.Bundle']"}),
            'error_message': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'traceback': ('django.db.models.fields.TextField', [], {'max_length': '32768'})
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
            'name': ('django.db.models.fields.TextField', [], {}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'value': ('django.db.models.fields.TextField', [], {})
        },
        'dashboard_app.softwarepackage': {
            'Meta': {'unique_together': "(('name', 'version'),)", 'object_name': 'SoftwarePackage'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'dashboard_app.softwarepackagescratch': {
            'Meta': {'object_name': 'SoftwarePackageScratch'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '128'})
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
        'dashboard_app.tag': {
            'Meta': {'object_name': 'Tag'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '256'})
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
            'name': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_cases'", 'to': "orm['dashboard_app.Test']"}),
            'test_case_id': ('django.db.models.fields.TextField', [], {}),
            'units': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'dashboard_app.testingeffort': {
            'Meta': {'object_name': 'TestingEffort'},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'testing_efforts'", 'to': "orm['lava_projects.Project']"}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'testing_efforts'", 'symmetrical': 'False', 'to': "orm['dashboard_app.Tag']"})
        },
        'dashboard_app.testresult': {
            'Meta': {'ordering': "('_order',)", 'object_name': 'TestResult'},
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
            'Meta': {'ordering': "['-import_assigned_date']", 'object_name': 'TestRun'},
            'analyzer_assigned_date': ('django.db.models.fields.DateTimeField', [], {}),
            'analyzer_assigned_uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '36'}),
            'bundle': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_runs'", 'to': "orm['dashboard_app.Bundle']"}),
            'devices': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': "orm['dashboard_app.HardwareDevice']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'import_assigned_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'packages': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': "orm['dashboard_app.SoftwarePackage']"}),
            'sources': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': "orm['dashboard_app.SoftwareSource']"}),
            'sw_image_desc': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': "orm['dashboard_app.Tag']"}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_runs'", 'to': "orm['dashboard_app.Test']"}),
            'time_check_performed': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'dashboard_app.testrundenormalization': {
            'Meta': {'object_name': 'TestRunDenormalization'},
            'count_fail': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'count_pass': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'count_skip': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'count_unknown': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'test_run': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'denormalization'", 'unique': 'True', 'primary_key': 'True', 'to': "orm['dashboard_app.TestRun']"})
        },
        'lava_projects.project': {
            'Meta': {'object_name': 'Project'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'identifier': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '100'}),
            'is_aggregate': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'registered_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'projects'", 'to': "orm['auth.User']"}),
            'registered_on': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
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
            'results_link': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '400', 'null': 'True', 'blank': 'True'}),
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
            'secret': ('django.db.models.fields.CharField', [], {'default': "'81eofh782e13qbzm7h65w03h8qznc0q4pwkjc1j7toqf9trqrzdbwtla5ncm6b7u93p4tr0foboqmnbjknedwgunjm606akx86n718iynunkzn3py0opudol6lys8hc5'", 'unique': 'True', 'max_length': '128'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'auth_tokens'", 'to': "orm['auth.User']"})
        }
    }

    complete_apps = ['dashboard_app', 'lava_scheduler_app']
    symmetrical = True
