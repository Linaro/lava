# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'ImageReportChart.chart_visibility'
        db.add_column(u'dashboard_app_imagereportchart', 'chart_visibility',
                      self.gf('django.db.models.fields.CharField')(default='chart', max_length=20),
                      keep_default=False)

    def backwards(self, orm):
        # Deleting field 'ImageReportChart.chart_visibility'
        db.delete_column(u'dashboard_app_imagereportchart', 'chart_visibility')

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
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'dashboard_app.attachment': {
            'Meta': {'object_name': 'Attachment'},
            'content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True'}),
            'content_filename': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mime_type': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'public_url': ('django.db.models.fields.URLField', [], {'max_length': '512', 'blank': 'True'})
        },
        u'dashboard_app.buglink': {
            'Meta': {'object_name': 'BugLink'},
            'bug_link': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'test_result': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'bug_links'", 'blank': 'True', 'to': u"orm['dashboard_app.TestResult']"}),
            'test_runs': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'bug_links'", 'blank': 'True', 'to': u"orm['dashboard_app.TestRun']"})
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
        u'dashboard_app.bundledeserializationerror': {
            'Meta': {'object_name': 'BundleDeserializationError'},
            'bundle': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'deserialization_error'", 'unique': 'True', 'primary_key': 'True', 'to': u"orm['dashboard_app.Bundle']"}),
            'error_message': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'traceback': ('django.db.models.fields.TextField', [], {'max_length': '32768'})
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
        u'dashboard_app.hardwaredevice': {
            'Meta': {'object_name': 'HardwareDevice'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'device_type': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'dashboard_app.image': {
            'Meta': {'object_name': 'Image'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'null': 'True', 'to': u"orm['dashboard_app.TestRunFilter']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '1024'})
        },
        u'dashboard_app.imagechartfilter': {
            'Meta': {'object_name': 'ImageChartFilter'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.TestRunFilter']", 'null': 'True', 'on_delete': 'models.SET_NULL'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.ImageReportChart']"}),
            'representation': ('django.db.models.fields.CharField', [], {'default': "'lines'", 'max_length': '20'})
        },
        u'dashboard_app.imagecharttest': {
            'Meta': {'unique_together': "(('image_chart_filter', 'test'),)", 'object_name': 'ImageChartTest'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart_filter': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.ImageChartFilter']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.Test']"})
        },
        u'dashboard_app.imagecharttestattribute': {
            'Meta': {'object_name': 'ImageChartTestAttribute'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart_test': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.ImageChartTest']"}),
            'name': ('django.db.models.fields.TextField', [], {})
        },
        u'dashboard_app.imagecharttestattributeuser': {
            'Meta': {'unique_together': "(('image_chart_test_attribute', 'user'),)", 'object_name': 'ImageChartTestAttributeUser'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart_test_attribute': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.ImageChartTestAttribute']"}),
            'is_visible': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'dashboard_app.imagecharttestcase': {
            'Meta': {'unique_together': "(('image_chart_filter', 'test_case'),)", 'object_name': 'ImageChartTestCase'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart_filter': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.ImageChartFilter']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'test_case': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.TestCase']"})
        },
        u'dashboard_app.imagecharttestcaseattribute': {
            'Meta': {'object_name': 'ImageChartTestCaseAttribute'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart_test_case': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.ImageChartTestCase']"}),
            'name': ('django.db.models.fields.TextField', [], {})
        },
        u'dashboard_app.imagecharttestcaseuser': {
            'Meta': {'unique_together': "(('image_chart_test_case', 'user'),)", 'object_name': 'ImageChartTestCaseUser'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart_test_case': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.ImageChartTestCase']"}),
            'is_visible': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'dashboard_app.imagecharttestuser': {
            'Meta': {'unique_together': "(('image_chart_test', 'user'),)", 'object_name': 'ImageChartTestUser'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart_test': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.ImageChartTest']"}),
            'is_visible': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'dashboard_app.imagechartuser': {
            'Meta': {'unique_together': "(('image_chart', 'user'),)", 'object_name': 'ImageChartUser'},
            'has_subscription': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_chart': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.ImageReportChart']"}),
            'is_legend_visible': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'start_date': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'dashboard_app.imagereport': {
            'Meta': {'object_name': 'ImageReport'},
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_report_group': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': u"orm['dashboard_app.ImageReportGroup']", 'null': 'True'}),
            'is_published': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '1024'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': u"orm['auth.User']"})
        },
        u'dashboard_app.imagereportchart': {
            'Meta': {'unique_together': "(('image_report', 'name'),)", 'object_name': 'ImageReportChart'},
            'chart_height': ('django.db.models.fields.PositiveIntegerField', [], {'default': '200'}),
            'chart_type': ('django.db.models.fields.CharField', [], {'default': "'pass/fail'", 'max_length': '20'}),
            'chart_visibility': ('django.db.models.fields.CharField', [], {'default': "'chart'", 'max_length': '20'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_report': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': u"orm['dashboard_app.ImageReport']"}),
            'is_data_table_visible': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_delta': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_interactive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_percentage': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'target_goal': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '5', 'blank': 'True'})
        },
        u'dashboard_app.imagereportgroup': {
            'Meta': {'object_name': 'ImageReportGroup'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '1024'})
        },
        u'dashboard_app.imageset': {
            'Meta': {'object_name': 'ImageSet'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'images': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['dashboard_app.Image']", 'symmetrical': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '1024'})
        },
        u'dashboard_app.namedattribute': {
            'Meta': {'unique_together': "(('object_id', 'name'),)", 'object_name': 'NamedAttribute'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'value': ('django.db.models.fields.TextField', [], {})
        },
        u'dashboard_app.pmqabundlestream': {
            'Meta': {'object_name': 'PMQABundleStream'},
            'bundle_stream': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': u"orm['dashboard_app.BundleStream']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'dashboard_app.softwarepackage': {
            'Meta': {'unique_together': "(('name', 'version'),)", 'object_name': 'SoftwarePackage'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        u'dashboard_app.softwarepackagescratch': {
            'Meta': {'object_name': 'SoftwarePackageScratch'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        u'dashboard_app.softwaresource': {
            'Meta': {'object_name': 'SoftwareSource'},
            'branch_revision': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'branch_url': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'branch_vcs': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'commit_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'default_params': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'project_name': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'test_params': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'})
        },
        u'dashboard_app.tag': {
            'Meta': {'object_name': 'Tag'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '256'})
        },
        u'dashboard_app.test': {
            'Meta': {'object_name': 'Test'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'test_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '1024'})
        },
        u'dashboard_app.testcase': {
            'Meta': {'unique_together': "(('test', 'test_case_id'),)", 'object_name': 'TestCase'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_cases'", 'to': u"orm['dashboard_app.Test']"}),
            'test_case_id': ('django.db.models.fields.TextField', [], {}),
            'units': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'dashboard_app.testdefinition': {
            'Meta': {'object_name': 'TestDefinition'},
            'content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'environment': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'format': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'location': ('django.db.models.fields.CharField', [], {'default': "'LOCAL'", 'max_length': '64'}),
            'mime_type': ('django.db.models.fields.CharField', [], {'default': "'text/plain'", 'max_length': '64'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '512'}),
            'target_dev_types': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'target_os': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '256'})
        },
        u'dashboard_app.testresult': {
            'Meta': {'ordering': "(u'_order',)", 'object_name': 'TestResult'},
            '_order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'comments': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lineno': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'measurement': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10', 'blank': 'True'}),
            'message': ('django.db.models.fields.TextField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'microseconds': ('django.db.models.fields.BigIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'relative_index': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'result': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'test_case': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'test_results'", 'null': 'True', 'to': u"orm['dashboard_app.TestCase']"}),
            'test_run': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_results'", 'to': u"orm['dashboard_app.TestRun']"}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        u'dashboard_app.testrun': {
            'Meta': {'ordering': "['-import_assigned_date']", 'object_name': 'TestRun'},
            'analyzer_assigned_date': ('django.db.models.fields.DateTimeField', [], {}),
            'analyzer_assigned_uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '36'}),
            'bundle': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_runs'", 'to': u"orm['dashboard_app.Bundle']"}),
            'devices': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': u"orm['dashboard_app.HardwareDevice']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'import_assigned_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'microseconds': ('django.db.models.fields.BigIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'packages': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': u"orm['dashboard_app.SoftwarePackage']"}),
            'sources': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': u"orm['dashboard_app.SoftwareSource']"}),
            'sw_image_desc': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'test_runs'", 'blank': 'True', 'to': u"orm['dashboard_app.Tag']"}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'test_runs'", 'to': u"orm['dashboard_app.Test']"}),
            'time_check_performed': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'dashboard_app.testrundenormalization': {
            'Meta': {'object_name': 'TestRunDenormalization'},
            'count_fail': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'count_pass': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'count_skip': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'count_unknown': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'test_run': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'denormalization'", 'unique': 'True', 'primary_key': 'True', 'to': u"orm['dashboard_app.TestRun']"})
        },
        u'dashboard_app.testrunfilter': {
            'Meta': {'unique_together': "(('owner', 'name'),)", 'object_name': 'TestRunFilter'},
            'build_number_attribute': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'bundle_streams': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['dashboard_app.BundleStream']", 'symmetrical': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'max_length': '1024'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'uploaded_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'+'", 'null': 'True', 'to': u"orm['auth.User']"})
        },
        u'dashboard_app.testrunfilterattribute': {
            'Meta': {'object_name': 'TestRunFilterAttribute'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'attributes'", 'to': u"orm['dashboard_app.TestRunFilter']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        u'dashboard_app.testrunfiltersubscription': {
            'Meta': {'unique_together': "(('user', 'filter'),)", 'object_name': 'TestRunFilterSubscription'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard_app.TestRunFilter']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'dashboard_app.testrunfiltertest': {
            'Meta': {'object_name': 'TestRunFilterTest'},
            'filter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tests'", 'to': u"orm['dashboard_app.TestRunFilter']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': u"orm['dashboard_app.Test']"})
        },
        u'dashboard_app.testrunfiltertestcase': {
            'Meta': {'object_name': 'TestRunFilterTestCase'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'test': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cases'", 'to': u"orm['dashboard_app.TestRunFilterTest']"}),
            'test_case': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': u"orm['dashboard_app.TestCase']"})
        }
    }

    complete_apps = ['dashboard_app']
