# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
import django.db.utils


class Migration(SchemaMigration):

    def forwards(self, orm):
        db.start_transaction()
        db.execute("""
CREATE OR REPLACE FUNCTION convert_to_integer(v_input text)
RETURNS INTEGER AS $a$
DECLARE v_int_value INTEGER DEFAULT NULL;
BEGIN
    BEGIN
        v_int_value := v_input::INTEGER;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;
RETURN v_int_value;
END;
$a$ LANGUAGE plpgsql;
        """)
        db.commit_transaction()

    def backwards(self, orm):
        db.execute("""DROP FUNCTION convert_to_integer (v_input text)""")

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
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
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
        'dashboard_app.image': {
            'Meta': {'object_name': 'Image'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'null': 'True', 'to': "orm['dashboard_app.TestRunFilter']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '1024'})
        },
        'dashboard_app.imagechartfilter': {
            'Meta': {'object_name': 'ImageChartFilter'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['dashboard_app.TestRunFilter']", 'null': 'True', 'on_delete': 'models.SET_NULL'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['dashboard_app.ImageReportChart']"}),
            'representation': ('django.db.models.fields.CharField', [], {'default': "'lines'", 'max_length': '20'})
        },
        'dashboard_app.imagecharttest': {
            'Meta': {'unique_together': "(('image_chart_filter', 'test'),)", 'object_name': 'ImageChartTest'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart_filter': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['dashboard_app.ImageChartFilter']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['dashboard_app.Test']"})
        },
        'dashboard_app.imagecharttestcase': {
            'Meta': {'unique_together': "(('image_chart_filter', 'test_case'),)", 'object_name': 'ImageChartTestCase'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart_filter': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['dashboard_app.ImageChartFilter']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'test_case': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['dashboard_app.TestCase']"})
        },
        'dashboard_app.imagechartuser': {
            'Meta': {'unique_together': "(('image_chart', 'user'),)", 'object_name': 'ImageChartUser'},
            'has_subscription': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['dashboard_app.ImageReportChart']"}),
            'is_legend_visible': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'start_date': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'dashboard_app.imagereport': {
            'Meta': {'object_name': 'ImageReport'},
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_report_group': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['dashboard_app.ImageReportGroup']", 'null': 'True'}),
            'is_published': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '1024'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']"})
        },
        'dashboard_app.imagereportchart': {
            'Meta': {'unique_together': "(('image_report', 'name'),)", 'object_name': 'ImageReportChart'},
            'chart_type': ('django.db.models.fields.CharField', [], {'default': "'pass/fail'", 'max_length': '20'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_report': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['dashboard_app.ImageReport']"}),
            'is_data_table_visible': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_interactive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'target_goal': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '5', 'blank': 'True'})
        },
        'dashboard_app.imagereportgroup': {
            'Meta': {'object_name': 'ImageReportGroup'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '1024'})
        },
        'dashboard_app.imageset': {
            'Meta': {'object_name': 'ImageSet'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'images': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['dashboard_app.Image']", 'symmetrical': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '1024'})
        },
        'dashboard_app.launchpadbug': {
            'Meta': {'object_name': 'LaunchpadBug'},
            'bug_id': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'test_runs': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'launchpad_bugs'", 'symmetrical': 'False', 'to': "orm['dashboard_app.TestRun']"})
        },
        'dashboard_app.namedattribute': {
            'Meta': {'unique_together': "(('object_id', 'name'),)", 'object_name': 'NamedAttribute'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'value': ('django.db.models.fields.TextField', [], {})
        },
        'dashboard_app.pmqabundlestream': {
            'Meta': {'object_name': 'PMQABundleStream'},
            'bundle_stream': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': "orm['dashboard_app.BundleStream']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
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
            'default_params': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'project_name': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'test_params': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'})
        },
        'dashboard_app.tag': {
            'Meta': {'object_name': 'Tag'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '256'})
        },
        'dashboard_app.test': {
            'Meta': {'object_name': 'Test'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'test_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '1024'})
        },
        'dashboard_app.testcase': {
            'Meta': {'unique_together': "(('test', 'test_case_id'),)", 'object_name': 'TestCase'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_cases'", 'to': "orm['dashboard_app.Test']"}),
            'test_case_id': ('django.db.models.fields.TextField', [], {}),
            'units': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'dashboard_app.testdefinition': {
            'Meta': {'object_name': 'TestDefinition'},
            'content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'environment': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'format': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'location': ('django.db.models.fields.CharField', [], {'default': "'LOCAL'", 'max_length': '64'}),
            'mime_type': ('django.db.models.fields.CharField', [], {'default': "'text/plain'", 'max_length': '64'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '512'}),
            'target_dev_types': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'target_os': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '256'})
        },
        'dashboard_app.testresult': {
            'Meta': {'ordering': "('_order',)", 'object_name': 'TestResult'},
            '_order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'comments': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
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
            'microseconds': ('django.db.models.fields.BigIntegerField', [], {'null': 'True', 'blank': 'True'}),
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
        'dashboard_app.testrunfilter': {
            'Meta': {'unique_together': "(('owner', 'name'),)", 'object_name': 'TestRunFilter'},
            'build_number_attribute': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'bundle_streams': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['dashboard_app.BundleStream']", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'max_length': '1024'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'uploaded_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'+'", 'null': 'True', 'to': "orm['auth.User']"})
        },
        'dashboard_app.testrunfilterattribute': {
            'Meta': {'object_name': 'TestRunFilterAttribute'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'attributes'", 'to': "orm['dashboard_app.TestRunFilter']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        'dashboard_app.testrunfiltersubscription': {
            'Meta': {'unique_together': "(('user', 'filter'),)", 'object_name': 'TestRunFilterSubscription'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['dashboard_app.TestRunFilter']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'dashboard_app.testrunfiltertest': {
            'Meta': {'object_name': 'TestRunFilterTest'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tests'", 'to': "orm['dashboard_app.TestRunFilter']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': "orm['dashboard_app.Test']"})
        },
        'dashboard_app.testrunfiltertestcase': {
            'Meta': {'object_name': 'TestRunFilterTestCase'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cases'", 'to': "orm['dashboard_app.TestRunFilterTest']"}),
            'test_case': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': "orm['dashboard_app.TestCase']"})
        }
    }

    complete_apps = ['dashboard_app']
