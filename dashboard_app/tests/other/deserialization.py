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
import contextlib
import datetime
import decimal
import hashlib
import os
import uuid

from django_testscenarios import (
    TestCase,
    TestCaseWithScenarios,
    TransactionTestCase,
    TransactionTestCaseWithScenarios,
)


from dashboard_app.tests import fixtures
from dashboard_app.models import (
        Attachment,
        Bundle,
        BundleDeserializationError,
        BundleStream,
        HardwareDevice,
        NamedAttribute,
        SoftwarePackage,
        Test,
        TestCase as TestCaseModel,
        TestResult,
        TestRun,
        )
from dashboard_app.helpers import (
        BundleDeserializer,
        DocumentError,
        )
from launch_control import models as client_models


class BundleDeserializerText2MemoryTestCase(TestCaseWithScenarios):

    # Required pieces of TestRun sub-document:
    # Since each nontrivial tests needs a bundle with TestRun I placed
    # this code here, the values are not relevant, they are valid and
    # will parse but are not checked.
    _TEST_RUN_BOILERPLATE = """
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                    "analyzer_assigned_date": "2010-12-31T23:59:59Z",
    """

    scenarios = [
        ('empty_bundle', {
            'json_text': '{}',
            'selectors': {
                'bundle': lambda bundle: bundle
            },
            'validators': [
                lambda self, selectors: self.assertTrue(
                    isinstance(selectors.bundle, client_models.DashboardBundle)),
                lambda self, selectors: self.assertEqual(
                    selectors.bundle.format, client_models.DashboardBundle.FORMAT),
                lambda self, selectors: self.assertEqual(
                    selectors.bundle.test_runs, []),
            ]
        }),
        ('bundle_parsing', {
            'json_text': """
            {
                "format": "Dashboard Bundle Format 1.0", 
                "test_runs": []
            }
            """,
            'selectors': {
                'bundle': lambda bundle: bundle
            },
            'validators': [
                lambda self, selectors: self.assertEqual(
                    selectors.bundle.format, "Dashboard Bundle Format 1.0"),
                lambda self, selectors: self.assertEqual(
                    selectors.bundle.test_runs, [])
            ]
        }),
        ('test_run_parsing', {
            'json_text': """
            {
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                    "analyzer_assigned_date": "2010-12-31T23:59:59Z"
                }]
            }
            """,
            'selectors': {
                'test_run': lambda bundle: bundle.test_runs[0]
            },
            'validators': [
                lambda self, selectors: self.assertTrue(
                    isinstance(selectors.test_run, client_models.TestRun)),
                lambda self, selectors: self.assertEqual(
                    selectors.test_run.test_id, "some_test_id"),
                lambda self, selectors: self.assertEqual(
                    selectors.test_run.test_results, []),
                lambda self, selectors: self.assertEqual(
                    selectors.test_run.analyzer_assigned_uuid,
                    uuid.UUID('1ab86b36-c23d-11df-a81b-002163936223')),
                lambda self, selectors: self.assertEqual(
                    # The format is described in datetime_proxy 
                    selectors.test_run.analyzer_assigned_date,
                    datetime.datetime(2010, 12, 31, 23, 59, 59, 0, None)),
                                    # YYYY  MM  DD  hh  mm  ss  ^  ^
                                    #                           microseconds
                                    #                              tzinfo
                lambda self, selectors: self.assertEqual(
                    selectors.test_run.time_check_performed, False),
                lambda self, selectors: self.assertEqual(
                    selectors.test_run.attributes, {}),
                lambda self, selectors: self.assertEqual(
                    selectors.test_run.attachments, {}),
                lambda self, selectors: self.assertEqual(
                    selectors.test_run.sw_context, None),
                lambda self, selectors: self.assertEqual(
                    selectors.test_run.hw_context, None),
                ]
        }),
        ('test_run_attachments', {
            'json_text': """
            {
                "test_runs": [{
                """ + _TEST_RUN_BOILERPLATE + """
                    "attachments": {
                        "file.txt": [
                            "line 1\\n",
                            "line 2\\n",
                            "line 3"
                        ]
                    }
                }]
            }
            """,
            'selectors': {
                'attachments': lambda bundle: bundle.test_runs[0].attachments
            },
            'validators': [
                lambda self, selectors: self.assertEqual(
                    selectors.attachments, {"file.txt": [
                        "line 1\n", "line 2\n", "line 3"]})
                ]
        }),
        ('test_run_attributes', {
            'json_text': """
            {
                "test_runs": [{
                """ + _TEST_RUN_BOILERPLATE + """
                    "attributes": {
                        "attr1": "value1",
                        "attr2": "value2"
                    }
                }]
            }
            """,
            'selectors': {
                'attributes': lambda bundle: bundle.test_runs[0].attributes
            },
            'validators': [
                lambda self, selectors: self.assertEqual(
                    selectors.attributes,
                    {"attr1": "value1", "attr2": "value2"})
                ]
        }),
        ('time_check_performed_is_parsed_as_bool', {
            'json_text': """
            {
                "test_runs": [{
            """ + _TEST_RUN_BOILERPLATE + """
                    "time_check_performed": true
                }, {
            """ + _TEST_RUN_BOILERPLATE + """
                    "time_check_performed": false
                }]
            }
            """,
            'selectors': {
                'test_run_0': lambda bundle: bundle.test_runs[0],
                'test_run_1': lambda bundle: bundle.test_runs[1]
            },
            'validators': [
                lambda self, selectors: self.assertEqual(
                    selectors.test_run_0.time_check_performed, True),
                lambda self, selectors: self.assertEqual(
                    selectors.test_run_1.time_check_performed, False)
            ]
        }),
        ('software_context_parsing', {
            'json_text': """
            {
                "test_runs": [{
            """ + _TEST_RUN_BOILERPLATE + """
                    "sw_context": {
                    }
                }]
            }
            """,
            'selectors': {
                'sw_context': lambda bundle: bundle.test_runs[0].sw_context,
            },
            'validators': [
                lambda self, selectors: self.assertTrue(
                    isinstance(selectors.sw_context,
                               client_models.SoftwareContext)),
                lambda self, selectors: self.assertEqual(
                    selectors.sw_context.packages, []),
                lambda self, selectors: self.assertEqual(
                    selectors.sw_context.sw_image, None),
            ]
        }),
        ('software_image_parsing', {
            'json_text': """
            {
                "test_runs": [{
            """ + _TEST_RUN_BOILERPLATE + """
                    "sw_context": {
                        "sw_image": {
                            "desc": "foobar"
                        }
                    }
                }]
            }
            """,
            'selectors': {
                'sw_image': lambda bundle: bundle.test_runs[0].sw_context.sw_image,
            },
            'validators': [
                lambda self, selectors: self.assertEqual(
                    selectors.sw_image.desc, "foobar"),
            ]
        }),
        ('software_package_parsing', {
            'json_text': """
            {
                "test_runs": [{
            """ + _TEST_RUN_BOILERPLATE + """
                    "sw_context": {
                        "packages": [{
                                "name": "foo",
                                "version": "1.0"
                            }
                        ]
                    }
                }]
            }
            """,
            'selectors': {
                'sw_package': lambda bundle: bundle.test_runs[0].sw_context.packages[0],
            },
            'validators': [
                lambda self, selectors: self.assertTrue(
                    isinstance(selectors.sw_package,
                               client_models.SoftwarePackage)),
                lambda self, selectors: self.assertEqual(
                    selectors.sw_package.name, "foo"),
                lambda self, selectors: self.assertEqual(
                    selectors.sw_package.version, "1.0"),
            ]
        }),
        ('hardware_context_defaults', {
            'json_text': """
            {
                "test_runs": [{
            """ + _TEST_RUN_BOILERPLATE + """
                    "hw_context": {
                    }
                }]
            }
            """,
            'selectors': {
                'hw_context': lambda bundle: bundle.test_runs[0].hw_context,
            },
            'validators': [
                lambda self, selectors: self.assertTrue(
                    isinstance(selectors.hw_context,
                               client_models.HardwareContext)),
                lambda self, selectors: self.assertEqual(
                    selectors.hw_context.devices, []),
            ]
        }),
        ('hardware_device_parsing', {
            'json_text': """
            {
                "test_runs": [{
            """ + _TEST_RUN_BOILERPLATE + """
                    "hw_context": {
                        "devices": [{
                            "device_type": "foo",
                            "description": "bar"
                        }
                    ]}
                }]
            }
            """,
            'selectors': {
                'hw_device': lambda bundle: bundle.test_runs[0].hw_context.devices[0],
            },
            'validators': [
                lambda self, selectors: self.assertTrue(
                    isinstance(selectors.hw_device,
                               client_models.HardwareDevice)),
                lambda self, selectors: self.assertEqual(
                    selectors.hw_device.device_type, "foo"),
                lambda self, selectors: self.assertEqual(
                    selectors.hw_device.description, "bar"),
                lambda self, selectors: self.assertEqual(
                    selectors.hw_device.attributes, {}),
            ]
        }),
        ('hardware_device_attributes_parsing', {
            'json_text': """
            {
                "test_runs": [{
            """ + _TEST_RUN_BOILERPLATE + """
                    "hw_context": {
                        "devices": [{
                            "device_type": "foo",
                            "description": "bar",
                            "attributes": {
                                "attr1": "value1",
                                "attr2": "value2"
                            }
                        }
                    ]}
                }]
            }
            """,
            'selectors': {
                'hw_device': lambda bundle: bundle.test_runs[0].hw_context.devices[0],
            },
            'validators': [
                lambda self, selectors: self.assertTrue(
                    isinstance(selectors.hw_device,
                               client_models.HardwareDevice)),
                lambda self, selectors: self.assertEqual(
                    selectors.hw_device.device_type, "foo"),
                lambda self, selectors: self.assertEqual(
                    selectors.hw_device.description, "bar"),
                lambda self, selectors: self.assertEqual(
                    selectors.hw_device.attributes,
                    {"attr1": "value1", "attr2": "value2"}),
            ]
        }),
        ('test_result_defaults', {
            'json_text': """
            {
                "test_runs": [{
            """ + _TEST_RUN_BOILERPLATE + """
                    "test_results": [{
                        "result": "pass"
                    }]
                }]
            }
            """,
            'selectors': {
                'test_result': lambda bundle: bundle.test_runs[0].test_results[0]
            },
            'validators': [
                lambda self, selectors: self.assertTrue(
                    isinstance(selectors.test_result,
                               client_models.TestResult)),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.result, "pass"),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.test_case_id, None),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.measurement, None),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.units, None),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.timestamp, None),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.duration, None),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.message, None),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.log_filename, None),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.log_lineno, None),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.attributes, {}),
            ]
        }),
        ('test_result_parsing', {
            'json_text': """
            {
                "test_runs": [{
            """ + _TEST_RUN_BOILERPLATE + """
                    "test_results": [{
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
                    }]
                }]
            }
            """,
            'selectors': {
                'test_result': lambda bundle: bundle.test_runs[0].test_results[0]
            },
            'validators': [
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.result, "unknown"),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.test_case_id, "some_test_case_id"),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.measurement, decimal.Decimal("1000.3")),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.units, "bogomips"),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.timestamp,
                    datetime.datetime(2010, 9, 17, 16, 34, 21, 0, None)),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.duration,
                    datetime.timedelta(days=1, seconds=1, microseconds=1)),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.message, "text message"),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.log_filename, "file.txt"),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.log_lineno, 15),
                lambda self, selectors: self.assertEqual(
                    selectors.test_result.attributes, {
                        "attr1": "value1",
                        "attr2": "value2"
                    }),
            ]
        }),
    ]

    def test_json_to_memory_model(self):
        deserializer = BundleDeserializer()
        obj = deserializer.json_to_memory_model(self.json_text)
        class Selectors:
            pass
        selectors = Selectors()
        for selector, callback in self.selectors.iteritems():
            setattr(selectors, selector, callback(obj))
        for validator in self.validators:
            validator(self, selectors)


class BundleDeserializerText2DatabaseTestCase(TransactionTestCase):

    json_text = """
    {
        "format": "Dashboard Bundle Format 1.0",
        "test_runs": [
            {
                "test_id": "some_test_id",
                "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                "analyzer_assigned_date": "2010-12-31T23:59:59Z",
                "time_check_performed": true,
                "test_results": [{
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
                }],
                "sw_context": {
                    "packages": [
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
    """

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
        super(BundleDeserializerText2DatabaseTestCase, self).setUp()
        self.s_bundle = fixtures.create_bundle(
            '/anonymous/', self.json_text, 'bundle.json')
        # Decompose the data here
        self.s_bundle.deserialize()
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
        Bundle.objects.all().delete()
        super(BundleDeserializerText2DatabaseTestCase, self).tearDown()

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


class BundleDeserializerFailureTestCase(TestCaseWithScenarios):

    scenarios = [
        ("empty_string", {"json_text": '', "cause": ValueError}),
        ("malformed_json", {"json_text": '{', "cause": ValueError}),
        # TypeError is caused by python calling the constructor or the
        # root document type (DashboardBundle) with invalid arguments
        ("bad_content", {
            "json_text": '{"mumbo": "jumbo"}',
            "cause": TypeError
        }),
        ("innocent_badness", {
            "json_text": '{"test_runs": "not an array of TestRun objects"}',
            "cause": TypeError, 
        }),
        ("invalid_format", {
            "json_text": '{"format": "MS Excel with 50 sheets"}',
            "cause": ValueError,
        }),
        ("invalid_datetime_value", {
            'json_text': """
            {
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                    "analyzer_assigned_date": "9999-99-99T99:99:99Z"
                }]
            }
            """,
            "cause": ValueError
        }),
        ("invalid_datetime_content", {
            'json_text': """
            {
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                    "analyzer_assigned_date": {"nobody expected": "a dictionary"}
                }]
            }
            """,
            "cause": TypeError
        }),
        ("invalid_uuid_value", {
            'json_text': """
            {
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
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
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "analyzer_assigned_uuid": 12345,
                    "analyzer_assigned_date": "2010-12-31T23:59:59Z"
                }]
            }
            """,
            "cause": TypeError
        }),
        ("invalid_timedelta_content", {
            'json_text': """
            {
            "test_runs": [{
                    "test_id":  "some_test_id",
                    "test_results": [],
                    "analyzer_assigned_uuid": "1ab86b36-c23d-11df-a81b-002163936223",
                    "analyzer_assigned_date": "2010-12-31T23:59:59Z",
                    "test_results": [{
                        "result": "pass",
                        "duration": 19123123123123123132,
                    }]
                }]
            }
            """,
            "cause": ValueError
        }),
    ]

    def test_json_to_memory_model_failure(self):
        deserializer = BundleDeserializer()
        try:
            deserializer.json_to_memory_model(self.json_text)
        except DocumentError as ex:
            self.assertEqual(self.cause, type(ex.cause))
        else:
            self.fail("Should have raised an exception")


class BundleDeserializerText2DatabaseFailureTestCase(TransactionTestCase):
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
        super(BundleDeserializerText2DatabaseFailureTestCase, self).setUp()

        self.assertEqual(Bundle.objects.count(), 0)
        self.assertEqual(BundleDeserializationError.objects.count(), 0)
        self.assertEqual(BundleStream.objects.count(), 0)

        self.s_bundle = fixtures.create_bundle(
            '/anonymous/', self.json_text, 'bundle.json')
        self.s_bundle.deserialize()

    def tearDown(self):
        Bundle.objects.all().delete()
        super(BundleDeserializerText2DatabaseFailureTestCase, self).tearDown()

    def test_bundle_deserialization_failed(self):
        self.assertFalse(self.s_bundle.is_deserialized)

    def test_bundle_count(self):
        self.assertEqual(Bundle.objects.count(), 1)

    def test_bundle_count(self):
        self.assertEqual(BundleDeserializationError.objects.count(), 1)

    def test_error_trace(self):
        self.assertEqual(
            self.s_bundle.deserialization_error.get().error_message,
            "column analyzer_assigned_uuid is not unique")

    def test_deserialization_failure_does_not_leave_junk_behind(self):
        self.assertRaises(
            TestRun.DoesNotExist, TestRun.objects.get,
            analyzer_assigned_uuid="1ab86b36-c23d-11df-a81b-002163936223")
