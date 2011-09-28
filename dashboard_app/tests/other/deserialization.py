# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Unit tests of the Dashboard application
"""
import datetime
import decimal

from django_testscenarios.ubertest import (
    TestCase,
    TestCaseWithScenarios,
    TransactionTestCase,
)
from django.contrib.auth.models import User
from linaro_dashboard_bundle.errors import DocumentFormatError
from linaro_json.schema import ValidationError
from linaro_json.extensions import datetime_extension


from dashboard_app.tests import fixtures
from dashboard_app.models import (
        Attachment,
        Bundle,
        BundleDeserializationError,
        BundleStream,
        HardwareDevice,
        NamedAttribute,
        SoftwarePackage,
        SoftwareSource,
        Test,
        TestCase as TestCaseModel,
        TestResult,
        TestRun,
        )
from dashboard_app.helpers import (
    BundleDeserializer,
    IBundleFormatImporter,
    BundleFormatImporter_1_0,
    BundleFormatImporter_1_1,
)



class IBundleFormatImporterTests(TestCase):

    def test_import_document_is_not_implemented(self):
        importer = IBundleFormatImporter()
        self.assertRaises(NotImplementedError,
                          importer.import_document, None, None)


class TestHelper(object):

    def getUniqueString(self, prefix=None, max_length=None):
        value = super(TestHelper, self).getUniqueString(prefix)
        if max_length is not None:
            if len(value) >= max_length:
                value = super(TestHelper, self).getUniqueString("short")
                if len(value) >= max_length:
                    raise ValueError("Unable to satisfy request for random string with max_length=%d" % max_length)
        return value

    def getUniqueStringForField(self, model, field_name):
        return self.getUniqueString(max_length=model._meta.get_field_by_name(field_name)[0].max_length)


class BundleFormatImporter_1_1Tests(TestHelper, TestCaseWithScenarios):

    scenarios = [
        ('with_commit_timestamp', {
            "commit_timestamp": datetime.datetime.now(),
        }),
        ('without_commit_timestamp', {
            "commit_timestamp": None
        })
    ]

    def c_getUniqueSoftwareSource(self):
        source = {
            "project_name": self.getUniqueStringForField(SoftwareSource, "project_name"),
            "branch_url": self.getUniqueStringForField(SoftwareSource, "branch_url"),
            "branch_vcs": self.getUniqueStringForField(SoftwareSource, "branch_vcs"),
            "branch_revision": self.getUniqueStringForField(SoftwareSource, "branch_revision"),
        }
        if self.commit_timestamp is not None:
            source["commit_timestamp"] = datetime_extension.to_json(self.commit_timestamp)
        return source

    def s_getUniqueTest(self):
        return Test.objects.create(
            test_id = self.getUniqueStringForField(Test, "test_id")
        )

    def s_getUniqueBundle(self):
        return Bundle.objects.create(
            bundle_stream = self.s_getUniqueBundleStream()
        )

    def s_getUniqueBundleStream(self):
        return BundleStream.objects.create(
            user = User.objects.create(username="legacy"),
            group = None
        )

    def s_getUniqueTestRun(self):
        return TestRun.objects.create(
            test = self.s_getUniqueTest(),
            bundle = self.s_getUniqueBundle(),
            analyzer_assigned_date = datetime.datetime.now(),
            analyzer_assigned_uuid = self.getUniqueStringForField(TestRun, "analyzer_assigned_uuid"),
        )

    def test_import_sources(self):
        c_test_run = {
            "software_context": {
                "sources": [
                    self.c_getUniqueSoftwareSource()
                    for i in range(3)
                ]
            }
        }
        s_test_run = self.s_getUniqueTestRun()
        importer = BundleFormatImporter_1_1()
        importer._import_sources(c_test_run, s_test_run)
        for c_source in c_test_run['software_context']['sources']:
            filter = dict(
                project_name = c_source['project_name'],
                branch_url = c_source['branch_url'],
                branch_vcs = c_source['branch_vcs'],
                branch_revision = str(c_source['branch_revision']),
                commit_timestamp = (
                    datetime_extension.from_json(
                        c_source["commit_timestamp"])
                    if "commit_timestamp" in c_source
                    else None)
            )
            s_source = SoftwareSource.objects.get(**filter)
            self.assertTrue(s_source is not None)
            self.assertTrue(s_source.pk is not None)
            self.assertTrue(s_source in s_test_run.sources.all())


class BundleBuilderMixin(object):
    """
    Helper mix-in for constructing bundle contents for unit testing
    """

    def getUniqueSoftwarePackage(self):
        return {
            "name": self.getUniqueStringForField(SoftwarePackage, "name"),
            "version": self.getUniqueStringForField(SoftwarePackage, "version")
        }

    def getUniqueSoftwareImage(self):
        return {
            "desc": self.getUniqueStringForField(TestRun, "sw_image_desc")
        }

    def getUniqueSoftwareContext(self, num_packages=None):
        if num_packages is None:
            num_packages = 5 # Arbitrary choice
        return {
            "sw_image": self.getUniqueSoftwareImage,
            "packages": [
                self.getUniqueSoftwarePackage() for i in range(num_packages)]
        }

    def getUniqueAttributes(self):
        attrs = {}
        for i in range(3):
            attrs[self.getUniqueStringForField(NamedAttribute, "name")] = \
                    self.getUniqueStringForField(NamedAttribute, "value")
        for i in range(3):
            attrs[self.getUniqueStringForField(NamedAttribute, "name")] = self.getUniqueInteger()
        return attrs

    def getUniqueHardwareDevice(self):
        return {
            "device_type": self.getUniqueStringForField(HardwareDevice, "device_type"),
            "description": self.getUniqueStringForField(HardwareDevice, "description"),
            "attributes": self.getUniqueAttributes(),
        }

    def getUniqueHardwareContext(self, num_devices=None):
        if num_devices is None:
            num_devices = 5 # Another arbitrary choice
        return {
            "devices": [
                self.getUniqueHardwareDevice() for i in range(num_devices)]
        }


class BundleFormatImporter_1_0Tests(
    TestHelper,
    TestCase,
    BundleBuilderMixin):

    def setUp(self):
        super(BundleFormatImporter_1_0Tests, self).setUp()
        self.importer = BundleFormatImporter_1_0()

    def test_get_sw_context_with_context(self):
        sw_context = self.getUniqueSoftwareContext()
        test_run = {"sw_context": sw_context}
        retval = self.importer._get_sw_context(test_run)
        self.assertEqual(retval, sw_context)

    def test_get_sw_context_without_context(self):
        test_run = {} # empty test run
        retval = self.importer._get_sw_context(test_run)
        self.assertEqual(retval, {})

    def test_get_hw_context_with_context(self):
        hw_context = self.getUniqueHardwareContext()
        test_run = {"hw_context": hw_context}
        retval = self.importer._get_hw_context(test_run)
        self.assertEqual(retval, hw_context)

    def test_get_hw_context_without_context(self):
        test_run = {} # empty test run
        retval = self.importer._get_hw_context(test_run)
        self.assertEqual(retval, {})

    def test_translate_result_string(self):
        self.assertEqual(
            self.importer._translate_result_string("pass"),
            TestResult.RESULT_PASS)
        self.assertEqual(
            self.importer._translate_result_string("fail"),
            TestResult.RESULT_FAIL)
        self.assertEqual(
            self.importer._translate_result_string("skip"),
            TestResult.RESULT_SKIP)
        self.assertEqual(
            self.importer._translate_result_string("unknown"),
            TestResult.RESULT_UNKNOWN)

    def test_translate_bogus_result_string(self):
        self.assertRaises(KeyError,
                          self.importer._translate_result_string,
                          "impossible result")


class BundleDeserializerSuccessTests(TestCaseWithScenarios):

    json_text = '''
    {
        "format": "Dashboard Bundle Format 1.0",
        "test_runs": [
            {
                "test_id": "some_test_id",
                "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                "analyzer_assigned_date": "2010-12-31T23:59:59Z",
                "time_check_performed": true,
                "test_results": [
                {
                    "test_case_id": "some_test_case_id",
                    "result": "unknown",
                    "measurement": 1000.3,
                    "units": "bogomips",
                    "timestamp": "2010-09-17T16:34:21Z",
                    "duration": "1d 1s 1us",
                    "message": "text message",
                    "log_filename": "file.txt",
                    "log_lineno": 15,
                    "attributes": {
                        "attr1": "value1",
                        "attr2": "value2"
                    }
                },
                {
                    "test_case_id": "some_test_case_id",
                    "result": "unknown"
                }
                ],
                "sw_context": {
                    "packages": [
                        {"name": "pkg1", "version": "1.0"},
                        {"name": "pkg1", "version": "1.0"},
                        {"name": "pkg2", "version": "0.5"}
                    ],
                    "sw_image": {
                        "desc": "Ubuntu 10.10"
                    }
                },
                "hw_context": {
                    "devices": [{
                        "device_type": "device.cpu",
                        "description": "ARM SoC",
                        "attributes": {
                            "MHz": "600",
                            "Revision": "3",
                            "Implementer": "0x41"
                        }}, {
                        "device_type": "device.board",
                        "description": "Beagle Board C4",
                        "attributes": {
                            "Revision": "C4"
                        }
                    }]
                },
                "attributes": {
                    "testrun attr1": "value1",
                    "testrun attr2": "value2"
                },
                "attachments": {
                    "file.txt": [
                        "line 1\\n",
                        "line 2\\n"
                    ]
                }
            }
        ]
    }
    '''

    scenarios = [
        ('with_evolution', {
            "prefer_evolution": True
        }),
        ('without_evolution', {
            "prefer_evolution": False
        })
    ]

    def _attrs2set(self, attrs):
        """
        Convert a collection of Attribute model instances into a python
        frozenset of tuples (name, value).
        """
        return frozenset([(attr.name, attr.value) for attr in attrs.all()])

    def _pkgs2set(self, pkgs):
        """
        Convert a collection of SoftwarePackage model instances into a python
        frozenset of tuples (name, version).
        """
        return frozenset([(package.name, package.version) for package in pkgs])

    def _devs2set(self, devs):
        """
        Convert a collection of HardareDevice model instances into a python
        frozenset of tuples (device_type, description, attributes).
        """
        return frozenset([(
            device.device_type,
            device.description,
            self._attrs2set(device.attributes)
        ) for device in devs])

    def setUp(self):
        super(BundleDeserializerSuccessTests, self).setUp()
        self.s_bundle = fixtures.create_bundle(
            '/anonymous/', self.json_text, 'bundle.json')
        # Decompose the data here
        self.s_bundle.deserialize(prefer_evolution=self.prefer_evolution)
        if not self.s_bundle.is_deserialized:
            raise AssertionError("Deserialzation failed:" + self.s_bundle.deserialization_error.get().traceback)
        # Here we trick a little, since there is just one of each of
        # those models we can select them like this, the tests below
        # validate that we did not pick up some random object by
        # matching all the properties.
        self.s_test = Test.objects.all()[0]
        self.s_test_case = TestCaseModel.objects.all()[0]
        self.s_test_run = TestRun.objects.all()[0]
        self.s_test_result = TestResult.objects.all()[0]
        self.s_attachment = Attachment.objects.all()[0]

    def tearDown(self):
        self.s_bundle.delete_files()
        super(BundleDeserializerSuccessTests, self).tearDown()

    def test_Test__test_id(self):
        self.assertEqual(self.s_test.test_id, "some_test_id")

    def test_Test__name_is_empty(self):
        # Bundles have no way to convey this meta-data
        # Unless the test was named manually by operator
        # and existed prior to import it will not have a name
        self.assertEqual(self.s_test.name, "")

    def test_TestCase__test_is_same_as__Test(self):
        self.assertEqual(self.s_test_case.test, self.s_test)

    def test_TestCase__test_case_id(self):
        self.assertEqual(self.s_test_case.test_case_id, "some_test_case_id")

    def test_TestCase__name_is_empty(self):
        # Same as test_Test__name_is_empty above
        self.assertEqual(self.s_test_case.name, "")

    def test_TestCase__units(self):
        self.assertEqual(self.s_test_case.units, "bogomips")

    def test_TestRun__bundle(self):
        self.assertEqual(self.s_test_run.bundle, self.s_bundle)

    def test_TestRun__test(self):
        self.assertEqual(self.s_test_run.test, self.s_test)

    def test_TestRun__analyzer_assigned_uuid(self):
        self.assertEqual(
            self.s_test_run.analyzer_assigned_uuid,
            "1ab86b36-c23d-11df-a81b-002163936223")

    def test_TestRun__analyzer_assigned_date(self):
        self.assertEqual(
            self.s_test_run.analyzer_assigned_date,
            datetime.datetime(2010, 12, 31, 23, 59, 59, 0, None))

    def test_TestRun__time_check_performed(self):
        self.assertEqual(self.s_test_run.time_check_performed, True)

    def test_TestRun__sw_image_desc(self):
        self.assertEqual(self.s_test_run.sw_image_desc, "Ubuntu 10.10")

    def test_TestRun__packages(self):
        self.assertEqual(
            self._pkgs2set(self.s_test_run.packages.all()),
            frozenset([
                ("pkg1", "1.0"),
                ("pkg2", "0.5")]))

    def test_TestRun__devices(self):
        self.assertEqual(
            self._devs2set(self.s_test_run.devices.all()),
            frozenset([
                ("device.cpu", "ARM SoC", frozenset([
                    ("MHz", "600"),
                    ("Revision", "3"),
                    ("Implementer", "0x41")])
                ),
                ("device.board", "Beagle Board C4", frozenset([
                    ("Revision", "C4")])
                )]))

    def test_TestRun__attributes(self):
        self.assertEqual(
            self._attrs2set(self.s_test_run.attributes.all()),
            frozenset([
                ("testrun attr1", "value1"),
                ("testrun attr2", "value2")]))

    def test_TestRun__attachments(self):
        self.assertEqual(
            self.s_test_run.attachments.all()[0],
            self.s_attachment)

    def test_TestRun__attachment__content_filename(self):
        self.assertEqual(
            self.s_attachment.content_filename,
            "file.txt")

    def test_TestRun__attachment__content(self):
        self.assertEqual(
            self.s_attachment.content.read(),
            "line 1\nline 2\n")

    def test_TestResult__test_run(self):
        self.assertEqual(self.s_test_result.test_run, self.s_test_run)

    def test_TestResult__test_case(self):
        self.assertEqual(self.s_test_result.test_case, self.s_test_case)

    def test_TestResult__result(self):
        self.assertEqual(self.s_test_result.result, TestResult.RESULT_UNKNOWN)

    def test_TestResult__measurement(self):
        self.assertEqual(
            self.s_test_result.measurement,
            decimal.Decimal("1000.3"))

    def test_TestResult__units(self):
        self.assertEqual(self.s_test_result.units, "bogomips")

    def test_TestResult__filename(self):
        self.assertEqual(self.s_test_result.filename, "file.txt")

    def test_TestResult__lineno(self):
        self.assertEqual(self.s_test_result.lineno, 15)

    def test_TestResult__message(self):
        self.assertEqual(self.s_test_result.message, "text message")

    def test_TestResult__duration(self):
        self.assertEqual(
            self.s_test_result.duration,
            datetime.timedelta(days=1, seconds=1, microseconds=1))

    def test_TestResult__timestamp(self):
        self.assertEqual(
            self.s_test_result.timestamp,
            datetime.datetime(2010, 9, 17, 16, 34, 21, 0, None))

    def test_TestResult__attributes(self):
        self.assertEqual(
            self._attrs2set(self.s_test_result.attributes.all()),
            frozenset([
                ("attr1", "value1"),
                ("attr2", "value2")]))


class Bundle13DeserializerSuccessTests(TestCase):

    json_text = '''
    {
        "format": "Dashboard Bundle Format 1.3",
        "test_runs": [
            {
                "test_id": "some_test_id",
                "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                "analyzer_assigned_date": "2010-12-31T23:59:59Z",
                "time_check_performed": true,
                "test_results": [ ],
                "tags": [
                    "tag-1",
                    "tag-2"
                ]
            }
        ]
    }
    '''
    
    def setUp(self):
        super(Bundle13DeserializerSuccessTests, self).setUp()
        self.s_bundle = fixtures.create_bundle(
            '/anonymous/', self.json_text, 'bundle.json')
        # Decompose the data here
        self.s_bundle.deserialize(prefer_evolution=False)
        if not self.s_bundle.is_deserialized:
            raise AssertionError("Deserialzation failed:" + self.s_bundle.deserialization_error.get().traceback)
        # Link to test run for easier testing
        self.s_test = self.s_bundle.test_runs.get()

    def tearDown(self):
        self.s_bundle.delete_files()
        super(Bundle13DeserializerSuccessTests, self).tearDown()

    def test_deserialize_tags(self):
        self.assertEqual(self.s_test.tags.count(), 2)
        self.assertEqual([tag.name for tag in self.s_test.tags.order_by('name').all()],
                         ["tag-1", "tag-2"])


class BundleDeserializerFailureTestCase(TestCaseWithScenarios):

    scenarios = [
        ("empty_string", {
            "json_text": '',
            "cause": ValueError,
        }),
        ("malformed_json", {
            "json_text": '{',
            "cause": ValueError,
        }),
        ("invalid_format", {
            "json_text": '{"format": "MS Excel with 50 sheets"}',
            "cause": DocumentFormatError
        }),
        ("invalid_datetime_value", {
            'json_text': """
            {
            "format": "Dashboard Bundle Format 1.0",
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "time_check_performed": false,
                    "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                    "analyzer_assigned_date": "9999-99-99T99:99:99Z"
                }]
            }
            """,
            "cause": ValidationError
        }),
        ("invalid_datetime_content", {
            'json_text': """
            {
            "format": "Dashboard Bundle Format 1.0",
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "time_check_performed": false,
                    "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                    "analyzer_assigned_date": {"nobody expected": "a dictionary"}
                }]
            }
            """,
            "cause": ValidationError
        }),
        ("invalid_uuid_value", {
            'json_text': """
            {
            "format": "Dashboard Bundle Format 1.0",
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "time_check_performed": false,
                    "analyzer_assigned_uuid": "string that is not an uuid",
                    "analyzer_assigned_date": "2010-12-31T23:59:59Z"
                }]
            }
            """,
            "cause": ValueError
        }),
        ("invalid_uuid_content", {
            'json_text': """
            {
            "format": "Dashboard Bundle Format 1.0",
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "time_check_performed": false,
                    "analyzer_assigned_uuid": 12345,
                    "analyzer_assigned_date": "2010-12-31T23:59:59Z"
                }]
            }
            """,
            "cause": ValidationError
        }),
        ("invalid_timedelta_content", {
            'json_text': """
            {
            "format": "Dashboard Bundle Format 1.0",
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "time_check_performed": false,
                    "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                    "analyzer_assigned_date": "2010-12-31T23:59:59Z",
                    "test_results": [{
                        "result": "pass",
                        "duration": 19123123123123123132
                    }]
                }]
            }
            """,
            "cause": ValidationError
        }),
    ]

    def setUp(self):
        super(BundleDeserializerFailureTestCase, self).setUp()
        self.s_bundle = fixtures.create_bundle(
            '/anonymous/', self.json_text, 'bundle.json')

    def tearDown(self):
        self.s_bundle.delete_files()
        super(BundleDeserializerFailureTestCase, self).tearDown()

    def test_deserializer_failure_without_evolution(self):
        try:
            BundleDeserializer().deserialize(self.s_bundle, prefer_evolution=False)
        except Exception as ex:
            self.assertIsInstance(ex, self.cause)
        else:
            self.fail("Should have raised an exception")

    def test_deserializer_failure_with_evolution(self):
        try:
            BundleDeserializer().deserialize(self.s_bundle, prefer_evolution=True)
        except Exception as ex:
            self.assertIsInstance(ex, self.cause)
        else:
            self.fail("Should have raised an exception")


class BundleDeserializerAtomicityTestCase(TransactionTestCase):
    # Importing this bundle will fail as analyzer_assigned_uuid is not
    # unique. Due to proper transaction handling the first test run
    # model instance will not be visible after the failed upload
    json_text = """
    {
        "format": "Dashboard Bundle Format 1.0",
        "test_runs": [
            {
                "test_id": "some_test_id",
                "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                "analyzer_assigned_date": "2010-12-31T23:59:59Z",
                "time_check_performed": true,
                "test_results": []
            }, {
                "test_id": "some_test_id",
                "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                "analyzer_assigned_date": "2010-12-31T23:59:59Z",
                "time_check_performed": true,
                "test_results": []
            }
        ]
    }
    """

    def setUp(self):
        super(BundleDeserializerAtomicityTestCase, self).setUp()
        self.s_bundle = fixtures.create_bundle(
            '/anonymous/', self.json_text, 'bundle.json')

    def tearDown(self):
        self.s_bundle.delete_files()
        super(BundleDeserializerAtomicityTestCase, self).tearDown()

    def test_bundle_deserialization_failed(self):
        self.s_bundle.deserialize()
        self.assertFalse(self.s_bundle.is_deserialized)

    def test_bundle_count(self):
        self.s_bundle.deserialize()
        self.assertEqual(Bundle.objects.count(), 1)

    def test_bundle_deserialization_error_count(self):
        self.s_bundle.deserialize()
        self.assertEqual(BundleDeserializationError.objects.count(), 1)

    def test_error_trace(self):
        self.s_bundle.deserialize()
        # The message depends on the database. This is a little ugly but it's
        # better than not knowing what really happened and hiding other
        # potential bugs that would otherwise be masked here.
        self.assertIn(
            self.s_bundle.deserialization_error.error_message, [
                'A test with UUID 1ab86b36-c23d-11df-a81b-002163936223 already exists',
                'column analyzer_assigned_uuid is not unique',
                u'duplicate key value violates unique constraint '
                u'"dashboard_app_testrun_analyzer_assigned_uuid_key"\n'])

    def test_deserialization_failure_does_not_leave_junk_behind(self):
        self.s_bundle.deserialize()
        self.assertRaises(
            TestRun.DoesNotExist, TestRun.objects.get,
            analyzer_assigned_uuid="1ab86b36-c23d-11df-a81b-002163936223")
