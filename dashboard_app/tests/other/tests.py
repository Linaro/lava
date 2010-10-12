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
import xmlrpclib

from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes import generic
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse, resolve
from django.db import models, IntegrityError
from django.test import TestCase, TransactionTestCase

from dashboard_app.tests.utils import (
    CSRFTestCase,
    TestClient,
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
from dashboard_app.dispatcher import (
        DjangoXMLRPCDispatcher,
        FaultCodes,
        xml_rpc_signature,
        )
from dashboard_app.xmlrpc import errors
from launch_control.thirdparty.mocker import Mocker, expect
from launch_control.utils.call_helper import ObjectFactoryMixIn
from launch_control import models as client_models


class BundleTest(TestCase):

    _NAME = "name"
    _SLUG = "slug"
    _GROUPNAME = "group"
    _USERNAME = "user"

    scenarios = [
        ('anonymous-no-slug', {
            'pathname': '/anonymous/',
            }),
        ('anonymous-with-slug', {
            'name': _NAME,
            'slug': _SLUG,
            'pathname': '/anonymous/slug/',
            }),
        ('personal-no-slug', {
            'username': _USERNAME,
            'pathname': '/personal/user/',
            }),
        ('personal-with-slug', {
            'username': _USERNAME,
            'name': _NAME,
            'slug': _SLUG,
            'pathname': '/personal/user/slug/',
            }),
        ('team-no-slug', {
            'groupname': _GROUPNAME,
            'pathname': '/team/group/',
            }),
        ('team-with-slug', {
            'groupname': _GROUPNAME,
            'name': _NAME,
            'slug': _SLUG,
            'pathname': '/team/group/slug/',
            }),
        ]

    groupname = None
    username = None
    group = None
    user = None
    name = ''
    slug = ''

    def setUp(self):
        super(BundleTest, self).setUp()
        if self.username is not None:
            self.user = User.objects.create(username='user')
        if self.groupname is not None:
            self.group = Group.objects.create(name='group')

    def test_creation(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        self.assertEqual(bundle_stream.user, self.user)
        self.assertEqual(bundle_stream.group, self.group)
        self.assertEqual(bundle_stream.name, self.name)
        self.assertEqual(bundle_stream.slug, self.slug)

    def test_team_named_stream(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        self.assertEqual(bundle_stream.pathname, self.pathname)

    def test_pathname_uniqueness(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        self.assertRaises(IntegrityError,
                BundleStream.objects.create,
                user=self.user, group=self.group, slug=self.slug,
                name=self.name)

    def test_pathname_update(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        old_pathname = bundle_stream.pathname
        bundle_stream.slug += "-changed"
        bundle_stream.save()
        self.assertNotEqual(bundle_stream.pathname, old_pathname)
        self.assertEqual(bundle_stream.pathname,
                bundle_stream._calc_pathname())


class BundleDeserializationTestCase(TestCase):

    scenarios = [
        ('dummy_import_failure', {
            'pathname': '/anonymous/',
            'content': 'bogus',
            'content_filename': 'test1.json',
        }),
    ]

    def setUp(self):
        super(BundleDeserializationTestCase, self).setUp()
        self.bundle = fixtures.create_bundle(
            self.pathname, self.content, self.content_filename)
        self.mocker = Mocker()

    def tearDown(self):
        super(BundleDeserializationTestCase, self).tearDown()
        self.bundle.delete()
        self.mocker.restore()
        self.mocker.verify()

    def test_deserialize_failure_leaves_trace(self):
        mock = self.mocker.patch(self.bundle)
        expect(mock._do_deserialize()).throw(Exception("boom"))
        self.mocker.replay()
        self.bundle.deserialize()
        self.assertFalse(self.bundle.is_deserialized)
        self.assertEqual(self.bundle.deserialization_error.get().error_message, "boom")

    def test_deserialize_ignores_deserialized_bundles(self):
        # just reply as we're not using mocker in this test case 
        self.mocker.replay()
        self.bundle.is_deserialized = True
        self.bundle.deserialize()
        self.assertTrue(self.bundle.is_deserialized)

    def test_deserialize_sets_is_serialized_on_success(self):
        mock = self.mocker.patch(self.bundle)
        expect(mock._do_deserialize())
        self.mocker.replay()
        self.bundle.deserialize()
        self.assertTrue(self.bundle.is_deserialized)

    def test_deserialize_clears_old_error_on_success(self):
        BundleDeserializationError.objects.create(
            bundle = self.bundle,
            error_message="not important").save()
        mock = self.mocker.patch(self.bundle)
        expect(mock._do_deserialize())
        self.mocker.replay()
        self.bundle.deserialize()
        # note we cannot check for self.bundle.deserialization_error
        # directly due to the way django handles operations that affect
        # existing instances (it does not touch them like storm would
        # IIRC).
        self.assertRaises(
            BundleDeserializationError.DoesNotExist,
            BundleDeserializationError.objects.get, bundle=self.bundle)


class BundleDeserializerText2MemoryTestCase(TestCase):

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

    def setUp(self):
        self.deserializer = BundleDeserializer()

    def test_json_to_memory_model(self):
        obj = self.deserializer.json_to_memory_model(self.json_text)
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


class BundleDeserializerFailureTestCase(TestCase):

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

    def setUp(self):
        self.deserializer = BundleDeserializer()

    def test_json_to_memory_model_failure(self):
        try:
            self.deserializer.json_to_memory_model(self.json_text)
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
        self.s_bundle = fixtures.create_bundle(
            '/anonymous/', self.json_text, 'bundle.json')
        self.s_bundle.deserialize()

    def test_bundle_deserialization_failed(self):
        self.assertFalse(self.s_bundle.is_deserialized)

    def test_error_trace(self):
        self.assertEqual(
            self.s_bundle.deserialization_error.get().error_message,
            "column analyzer_assigned_uuid is not unique")

    def test_deserialization_failure_does_not_leave_junk_behind(self):
        self.assertRaises(
            TestRun.DoesNotExist, TestRun.objects.get,
            analyzer_assigned_uuid="1ab86b36-c23d-11df-a81b-002163936223")


class TestConstructionTestCase(TestCase):

    scenarios = [
        ('simple1', {
            'test_id': 'org.linaro.testheads.android',
            'name': "Android test suite"}),
        ('simple2', {
            'test_id': 'org.mozilla.unit-tests',
            'name': "Mozilla unit test collection"})
    ]

    def test_construction(self):
        test = Test(test_id = self.test_id, name = self.name)
        test.save()
        self.assertEqual(test.test_id, self.test_id)
        self.assertEqual(test.name, self.name)

    def test_test_id_uniqueness(self):
        test = Test(test_id = self.test_id, name = self.name)
        test.save()
        test2 = Test(test_id = self.test_id)
        self.assertRaises(IntegrityError, test2.save)




class TestRunConstructionTestCase(TestCase):

    _TEST_ID = "test_id"
    _BUNDLE_PATHNAME = "/anonymous/"
    _BUNDLE_CONTENT_FILENAME = "bundle.txt"
    _BUNDLE_CONTENT = "content not relevant"

    def test_construction(self):
        test = Test.objects.create(test_id=self._TEST_ID)
        analyzer_assigned_uuid = '9695b58e-bfe9-11df-a9a4-002163936223'
        analyzer_assigned_date = datetime.datetime(2010, 9, 14, 12, 20, 00)
        time_check_performed = False
        with fixtures.created_bundles([(
            self._BUNDLE_PATHNAME, self._BUNDLE_CONTENT_FILENAME,
            self._BUNDLE_CONTENT), ]) as bundles:
            test_run = TestRun(
                bundle = bundles[0],
                test = test,
                analyzer_assigned_uuid = analyzer_assigned_uuid,
                analyzer_assigned_date = analyzer_assigned_date,
            )
            test_run.save()
            self.assertEqual(test_run.bundle, bundles[0])
            self.assertEqual(test_run.test, test)
            self.assertEqual(test_run.analyzer_assigned_uuid,
                             analyzer_assigned_uuid)


class TestResultDurationTestCase(TestCase):

    scenarios = [
        ('none_is_null', {
            'duration': None,
            'microseconds': None,
        }),
        ('0_is_0', {
            'duration': datetime.timedelta(days=0, seconds=0, microseconds=0),
            'microseconds': 0,
        }),
        ('microseconds_are_just_microseconds', {
            'duration': datetime.timedelta(microseconds=1),
            'microseconds': 1,
        }),
        ('second_is_10e6_microseconds', {
            'duration': datetime.timedelta(seconds=1),
            'microseconds': 10**6,
        }),
        ('day_is_24_times_60_times_60_times_10e6_microseconds', {
            'duration': datetime.timedelta(days=1),
            'microseconds': 24 * 60 * 60 * 10 ** 6,
        }),
        ('microseconds_seconds_and_days_are_used', {
            'duration': datetime.timedelta(days=1, seconds=1, microseconds=1),
            'microseconds': (
                24 * 60 * 60 * (10 ** 6) +
                10 ** 6 +
                1)
        }),
    ]

    def test_duration_to_microseconds(self):
        obj = TestResult()
        obj.duration = self.duration
        self.assertEqual(self.microseconds, obj.microseconds)

    def test_microseconds_to_duration(self):
        obj = TestResult()
        obj.microseconds = self.microseconds
        self.assertEqual(self.duration, obj.duration)


class BundleStreamManagerAllowedForAnyoneTestCase(TestCase):

    _USER = 'user'
    _GROUP = 'group'
    _SLUG = 'slug'

    scenarios = [
        ('empty', {
            'bundle_streams': [],
            'expected_pathnames': [],
            }),
        ('public_streams_are_listed', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': 'other'},
                {'slug': 'and-another'},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/and-another/',
                '/anonymous/other/',
                ],
            }),
        ('private_streams_are_hidden', {
            'bundle_streams': [
                {'user': _USER},
                ],
            'expected_pathnames': [],
            }),
        ('team_streams_are_hidden', {
            'bundle_streams': [
                {'group': _GROUP},
                ],
            'expected_pathnames': [],
            }),
        ('mix_and_match_works', {
            'bundle_streams': [
                {'group': _GROUP, 'slug': _SLUG},
                {'group': _GROUP},
                {'slug': ''},
                {'slug': _SLUG},
                {'user': _GROUP, 'slug': _SLUG},
                {'user': _USER},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/{0}/'.format(_SLUG),
                ],
            }),
        ]

    def test_allowed_for_anyone(self):
        with fixtures.created_bundle_streams(self.bundle_streams):
            pathnames = [bundle_stream.pathname for bundle_stream in
                    BundleStream.objects.allowed_for_anyone().order_by('pathname')]
            self.assertEqual(pathnames, self.expected_pathnames)


class BundleStreamManagerAllowedForUserTestCase(TestCase):

    _USER = 'user'
    _USER2 = 'user2'
    _GROUP = 'group'
    _GROUP2 = 'group2'
    _SLUG = 'slug'

    scenarios = [
        ('empty', {
            'bundle_streams': [],
            'expected_pathnames': [],
            }),
        ('public_streams_are_listed', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': 'other'},
                {'slug': 'and-another'},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/and-another/',
                '/anonymous/other/',
                ],
            }),
        ('owned_private_streams_are_listed', {
            'bundle_streams': [
                {'user': _USER},
                ],
            'expected_pathnames': [
                '/personal/{0}/'.format(_USER),
                ],
            }),
        ('other_private_streams_are_hidden', {
            'bundle_streams': [
                {'user': _USER2},
                ],
            'expected_pathnames': [],
            }),
        ('shared_team_streams_are_listed', {
            'bundle_streams': [
                {'group': _GROUP},
                ],
            'expected_pathnames': [
                '/team/{0}/'.format(_GROUP),
                ],
            }),
        ('other_team_streams_are_hidden', {
            'bundle_streams': [
                {'group': _GROUP2},
                ],
            'expected_pathnames': [],
            }),
        ('mix_and_match_works', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': _SLUG},
                {'user': _USER, 'slug': _SLUG},
                {'user': _USER},
                {'group': _GROUP, 'slug': _SLUG},
                {'group': _GROUP},
                # things which should not be accessible
                {'user': _USER2, 'slug': _SLUG},
                {'user': _USER2},
                {'group': _GROUP2, 'slug': _SLUG},
                {'group': _GROUP2},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/{0}/'.format(_SLUG),
                '/personal/{0}/'.format(_USER),
                '/personal/{0}/{1}/'.format(_USER, _SLUG),
                '/team/{0}/'.format(_GROUP),
                '/team/{0}/{1}/'.format(_GROUP, _SLUG),
                ],
            }),
        ]

    def test_allowed_for_user(self):
        with fixtures.created_bundle_streams(self.bundle_streams) as all:
            user = User.objects.get_or_create(username=self._USER)[0]
            user.save()
            group = Group.objects.get_or_create(name=self._GROUP)[0]
            group.save()
            user.groups.add(group)
            pathnames = [bundle_stream.pathname for bundle_stream in
                    BundleStream.objects.allowed_for_user(user).order_by('pathname')]
            self.assertEqual(pathnames, self.expected_pathnames)


class BundleStreamUploadRightTests(TestCase):

    def test_owner_can_access_personal_stream(self):
        user = User.objects.create(username="test-user")
        bundle_stream = BundleStream.objects.create(user=user)
        self.assertTrue(bundle_stream.can_access(user))

    def test_other_users_cannot_access_personal_streams(self):
        owner = User.objects.create(username="stream-owner")
        unrelated_user = User.objects.create(username="other-user")
        bundle_stream = BundleStream.objects.create(user=owner)
        self.assertFalse(bundle_stream.can_access(unrelated_user))

    def test_anonymous_users_cannot_access_personal_streams(self):
        owner = User.objects.create(username="stream-owner")
        bundle_stream = BundleStream.objects.create(user=owner)
        self.assertFalse(bundle_stream.can_access(None))

    def test_group_member_can_access_team_streams(self):
        group = Group.objects.create(name="members")
        user = User.objects.create(username="user")
        user.groups.add(group)
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertTrue(bundle_stream.can_access(user))

    def test_other_users_cannot_access_team_streams(self):
        group = Group.objects.create(name="members")
        member = User.objects.create(username="user")
        member.groups.add(group)
        unrelated_user = User.objects.create(username="other-user")
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertFalse(bundle_stream.can_access(unrelated_user))

    def test_anonymous_users_cannot_access_team_streams(self):
        group = Group.objects.create(name="members")
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertFalse(bundle_stream.can_access(None))

    def test_anonymous_users_can_access_public_streams(self):
        bundle_stream = BundleStream.objects.create(user=None, group=None)
        self.assertTrue(bundle_stream.can_access(None))

    def test_authorized_users_can_access_public_streams(self):
        user = User.objects.create(username="user")
        bundle_stream = BundleStream.objects.create(user=None, group=None)
        self.assertTrue(bundle_stream.can_access(user))


class BundleTests(TestCase, ObjectFactoryMixIn):

    class Dummy:
        class Bundle:
            @property
            def bundle_stream(self):
                return BundleStream.objects.get_or_create(slug="foobar")[0]
            uploaded_by = None
            content = ContentFile("file content")
            content_filename = "file.txt"

    def test_construction(self):
        dummy, bundle = self.make_and_get_dummy(Bundle)
        bundle.content.save(bundle.content_filename, dummy.content)
        # reset the dummy content file pointer for subsequent tests
        dummy.content.seek(0)
        content = dummy.content.read()

        bundle.save()
        try:
            self.assertEqual(bundle.bundle_stream, dummy.bundle_stream)
            self.assertEqual(bundle.uploaded_by, dummy.uploaded_by)
            #self.assertEqual(bundle.uploaded_on, mocked_value_of_time.now)
            self.assertEqual(bundle.is_deserialized, False)
            bundle.content.open()
            self.assertEqual(bundle.content.read(), content)
            bundle.content.close()
            self.assertEqual(bundle.content_sha1,
                    hashlib.sha1(content).hexdigest())
            self.assertEqual(bundle.content_filename,
                    dummy.content_filename)
        finally:
            bundle.delete()


class TestAPI(object):
    """
    Test API that gets exposed by the dispatcher for test runs.
    """

    @xml_rpc_signature()
    def ping(self):
        """
        Return "pong" message
        """
        return "pong"

    def echo(self, arg):
        """
        Return the argument back to the caller
        """
        return arg

    def boom(self, code, string):
        """
        Raise a Fault exception with the specified code and string
        """
        raise xmlrpclib.Fault(code, string)

    def internal_boom(self):
        """
        Raise a regular python exception (this should be hidden behind
        an internal error fault)
        """
        raise Exception("internal boom")


class DjangoXMLRPCDispatcherTestCase(TestCase):

    def setUp(self):
        super(DjangoXMLRPCDispatcherTestCase, self).setUp()
        self.dispatcher = DjangoXMLRPCDispatcher()
        self.dispatcher.register_instance(TestAPI())

    def xml_rpc_call(self, method, *args):
        """
        Perform XML-RPC call on our internal dispatcher instance

        This calls the method just like we would have normally from our view.
        All arguments are marshaled and un-marshaled. XML-RPC fault exceptions
        are raised like normal python exceptions (by xmlrpclib.loads)
        """
        request = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.dispatcher._marshaled_dispatch(request)
        # This returns return value wrapped in a tuple and method name
        # (which we don't have here as this is a response message).
        return xmlrpclib.loads(response)[0][0]


class DjangoXMLRPCDispatcherTests(DjangoXMLRPCDispatcherTestCase):

    def test_standard_fault_code_for_missing_method(self):
        try:
            self.xml_rpc_call("method_that_hopefully_does_not_exist")
        except xmlrpclib.Fault as ex:
            self.assertEqual(
                    ex.faultCode,
                    FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND)
        else:
            self.fail("Calling missing method did not raise an exception")

    def test_ping(self):
        retval = self.xml_rpc_call("ping")
        self.assertEqual(retval, "pong")

    def test_echo(self):
        self.assertEqual(self.xml_rpc_call("echo", 1), 1)
        self.assertEqual(self.xml_rpc_call("echo", "string"), "string")
        self.assertEqual(self.xml_rpc_call("echo", 1.5), 1.5)

    def test_boom(self):
        self.assertRaises(xmlrpclib.Fault,
                self.xml_rpc_call, "boom", 1, "str")


class DjangoXMLRPCDispatcherFaultCodeTests(DjangoXMLRPCDispatcherTestCase):

    scenarios = [
            ('method_not_found', {
                'method': "method_that_hopefully_does_not_exist",
                'faultCode': FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND,
                }),
            ('internal_error', {
                'method': "internal_boom",
                'faultCode': FaultCodes.ServerError.INTERNAL_XML_RPC_ERROR,
                }),
            ]

    def test_standard_fault_codes(self):
        try:
            self.xml_rpc_call(self.method)
        except xmlrpclib.Fault as ex:
            self.assertEqual(ex.faultCode, self.faultCode)
        else:
            self.fail("Exception not raised")


class DashboardViewsTestCase(TestCase):
    """
    Helper class that ensures dashboard views are mapped in URLs the way
    we expect, regardless of actual deployment.
    """
    urls = 'dashboard_app.urls'

    def setUp(self):
        super(DashboardViewsTestCase, self).setUp()
        self.old_LANGUAGES = settings.LANGUAGES
        self.old_LANGUAGE_CODE = settings.LANGUAGE_CODE
        settings.LANGUAGES = (('en', 'English'),)
        settings.LANGUAGE_CODE = 'en'
        self.old_TEMPLATE_DIRS = settings.TEMPLATE_DIRS
        settings.TEMPLATE_DIRS = (
            os.path.join(
                os.path.dirname(__file__),
                'templates'
            )
        ,)

    def tearDown(self):
        settings.LANGUAGES = self.old_LANGUAGES
        settings.LANGUAGE_CODE = self.old_LANGUAGE_CODE
        settings.TEMPLATE_DIRS = self.old_TEMPLATE_DIRS
        super(DashboardViewsTestCase, self).tearDown()


class DashboardXMLRPCViewsTestCase(DashboardViewsTestCase):
    """
    Helper base class for doing XML-RPC requests
    """

    def setUp(self):
        super(DashboardXMLRPCViewsTestCase, self).setUp()
        self.endpoint_path = reverse("dashboard_app.dashboard_xml_rpc_handler")

    def xml_rpc_call(self, method, *args):
        request_body = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.client.post(self.endpoint_path,
                request_body, "text/xml")
        return xmlrpclib.loads(response.content)[0][0]


class TestClientTest(TestCase):

    _USER = "user"

    urls = 'dashboard_app.tests.urls'

    def setUp(self):
        super(TestClientTest, self).setUp()
        self.client = TestClient()
        self.user = User(username=self._USER)
        self.user.save()

    def test_auth(self):
        self.client.login_user(self.user)
        response = self.client.get("/auth-test/")
        self.assertEqual(response.content, self._USER)

    def test_no_auth(self):
        response = self.client.get("/auth-test/")
        self.assertEqual(response.content, '')


class DashboardAPITests(DashboardXMLRPCViewsTestCase):

    def test_xml_rpc_help_returns_200(self):
        response = self.client.get("/xml-rpc/")
        self.assertEqual(response.status_code, 200)

    def test_help_page_lists_all_methods(self):
        from dashboard_app.views import DashboardDispatcher as dispatcher
        expected_methods = []
        for name in dispatcher.system_listMethods():
            expected_methods.append({
                'name': name,
                'signature': dispatcher.system_methodSignature(name),
                'help': dispatcher.system_methodHelp(name)
                })
        response = self.client.get("/xml-rpc/")
        self.assertEqual(response.context['methods'], expected_methods)

    def test_get_request_shows_help(self):
        response = self.client.get("/xml-rpc/")
        self.assertTemplateUsed(response, "dashboard_app/api.html")

    def test_empty_post_request_shows_help(self):
        response = self.client.post("/xml-rpc/")
        self.assertTemplateUsed(response, "dashboard_app/api.html")

    def test_version(self):
        from dashboard_app import __version__
        self.assertEqual(self.xml_rpc_call('version'),
                ".".join(map(str, __version__)))


class DashboardAPIStreamsTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('empty', {
            'streams': [],
            'expected_response': [],
            }),
        ('one_public_stream', {
            'streams': [
                {'slug': '', 'user': None, 'group': None}],
            'expected_response': [{
                'bundle_count': 0,
                'user': '',
                'group': '',
                'name': '',
                'pathname': '/anonymous/'}],
            }),
        ('private_streams_are_not_shown', {
            'streams': [
                {'slug': '', 'user': 'joe', 'group': None},
                {'slug': '', 'user': None, 'group': None}],
            'expected_response': [{
                'bundle_count': 0,
                'user': '',
                'group': '',
                'name': '',
                'pathname': '/anonymous/'}],
            }),
        ('team_streams_are_not_shown', {
            'streams': [
                {'slug': '', 'user': None, 'group': 'group'},
                {'slug': '', 'user': None, 'group': None}],
            'expected_response': [{
                'bundle_count': 0,
                'user': '',
                'group': '',
                'name': '',
                'pathname': '/anonymous/'}],
            }),
        ]

    def test_streams(self):
        with fixtures.created_bundle_streams(self.streams):
            response = self.xml_rpc_call('streams')
            self.assertEqual(response, self.expected_response)


class DashboardAPIBundlesTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('empty', {
            'query': '/anonymous/',
            'bundle_streams': [{}], # make one anonymous stream so that we don't get 404 accessing missing one
            'bundles': [],
            'expected_results': [],
            }),
        ('several_bundles_we_can_see', {
            'query': '/anonymous/',
            'bundle_streams': [],
            'bundles': [
                ('/anonymous/', 'test1.json', '{"foobar": 5}'),
                ('/anonymous/', 'test2.json', '{"froz": "bot"}'),
                ],
            'expected_results': [{
                'content_filename': 'test1.json',
                'content_sha1': '72996acd68de60c766b60c2ca6f6169f67cdde19',
                }, {
                'content_filename': 'test2.json',
                'content_sha1': '67dd49730d4e3b38b840f3d544d45cad74bcfb09',
                }],
            }),
        ('several_bundles_in_other_stream', {
            'query': '/anonymous/other/',
            'bundle_streams': [],
            'bundles': [
                ('/anonymous/', 'test3.json', '{}'),
                ('/anonymous/other/', 'test4.json', '{"x": true}'),
                ],
            'expected_results': [{
                'content_filename': 'test4.json',
                'content_sha1': 'bac148f29c35811441a7b4746a022b04c65bffc0',
                }],
            }),
        ]

    def test_bundles(self):
        """
        Make a bunch of bundles (all in a public branch) and check that
        they are returned by the XML-RPC request.
        """
        with contextlib.nested(
                fixtures.created_bundle_streams(self.bundle_streams),
                fixtures.created_bundles(self.bundles)):
            results = self.xml_rpc_call('bundles', self.query)
            self.assertEqual(len(results), len(self.expected_results))
            with fixtures.test_loop(zip(results, self.expected_results)) as loop_items:
                for result, expected_result in loop_items:
                    self.assertEqual(
                            result['content_filename'],
                            expected_result['content_filename'])
                    self.assertEqual(
                            result['content_sha1'],
                            expected_result['content_sha1'])


class DashboardAPIBundlesFailureTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('no_such_stream', {
            'bundle_streams': [],
            'query': '/anonymous/',
            'expected_faultCode': errors.NOT_FOUND,
            }),
        ('no_anonymous_access_to_personal_streams', {
            'bundle_streams': [{'user': 'user'}],
            'query': '/personal/user/',
            'expected_faultCode': errors.FORBIDDEN,
            }),
        ('no_anonymous_access_to_team_streams', {
            'bundle_streams': [{'group': 'group'}],
            'query': '/team/group/',
            'expected_faultCode': errors.FORBIDDEN,
            }),
        ]

    def test_bundles_failure(self):
        with fixtures.created_bundle_streams(self.bundle_streams):
            try:
                self.xml_rpc_call("bundles", self.query)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, self.expected_faultCode)
            else:
                self.fail("Should have raised an exception")


class DashboardAPIGetTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('bundle_we_can_access', {
            'content_sha1': '72996acd68de60c766b60c2ca6f6169f67cdde19',
            'bundles': [
                ('/anonymous/', 'test1.json', '{"foobar": 5}'),
                ('/anonymous/', 'test2.json', '{"froz": "bot"}'),
                ],
            'expected_result': {
                'content_filename': 'test1.json',
                'content': '{"foobar": 5}',
                }
            }),
        ]

    def test_get(self):
        """
        Make a bunch of bundles (all in a public branch) and check that
        we can get them back by calling get()
        """
        with fixtures.created_bundles(self.bundles):
            result = self.xml_rpc_call('get', self.content_sha1)
            self.assertTrue(isinstance(result, dict))
            self.assertEqual(
                    result['content_filename'],
                    self.expected_result['content_filename'])
            self.assertEqual(
                    result['content'],
                    self.expected_result['content'])


class DashboardAPIGetFailureTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('bad_sha1', {
            'content_sha1': '',
            'faultCode': errors.NOT_FOUND
            }),
        ('no_access_to_personal_bundles', {
            'bundles': [
                ('/personal/bob/', 'test1.json', '{"foobar": 5}'),
                ],
            'faultCode': errors.FORBIDDEN
            }),
        ('no_access_to_named_personal_bundles', {
            'bundles': [
                ('/personal/bob/some-name/', 'test1.json', '{"foobar": 5}'),
                ],
            'faultCode': errors.FORBIDDEN
            }),
        ('no_access_to_team_bundles', {
            'bundles': [
                ('/team/members/', 'test1.json', '{"foobar": 5}'),
                ],
            'faultCode': errors.FORBIDDEN
            }),
        ('no_access_to_named_team_bundles', {
            'bundles': [
                ('/team/members/some-name/', 'test1.json', '{"foobar": 5}'),
                ],
            'faultCode': errors.FORBIDDEN
            }),
        ]

    bundles = []
    content_sha1='72996acd68de60c766b60c2ca6f6169f67cdde19'

    def test_get_failure(self):
        with fixtures.created_bundles(self.bundles):
            try:
                self.xml_rpc_call('get', self.content_sha1)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, self.faultCode)
            else:
                self.fail("Should have raised an exception")


class DashboardAPIPutTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('store_to_public_stream', {
            'bundle_streams': [{}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/',
            }),
        ('store_to_public_named_stream', {
            'bundle_streams': [{'slug': 'some-name'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/some-name/',
            }),
        ]

    def test_put(self):
        with fixtures.created_bundle_streams(self.bundle_streams):
            content_sha1 = self.xml_rpc_call("put",
                    self.content, self.content_filename, self.pathname)
            stored = Bundle.objects.get(content_sha1=content_sha1)
            try:
                self.assertEqual(stored.content_sha1, content_sha1)
                self.assertEqual(stored.content.read(), self.content)
                self.assertEqual(
                    stored.content_filename, self.content_filename)
                self.assertEqual(stored.bundle_stream.pathname, self.pathname)
            finally:
                stored.delete()


class DashboardAPIPutFailureTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('store_to_personal_stream', {
            'bundle_streams': [{'user': 'joe'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/personal/joe/',
            'faultCode': errors.FORBIDDEN,
            }),
        ('store_to_named_personal_stream', {
            'bundle_streams': [{'user': 'joe', 'slug': 'some-name'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/personal/joe/some-name/',
            'faultCode': errors.FORBIDDEN,
            }),
        ('store_to_team_stream', {
            'bundle_streams': [{'group': 'members'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/team/members/',
            'faultCode': errors.FORBIDDEN,
            }),
        ('store_to_named_team_stream', {
            'bundle_streams': [{'group': 'members', 'slug': 'some-name'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/team/members/some-name/',
            'faultCode': errors.FORBIDDEN,
            }),
        ('store_to_missing_stream', {
            'bundle_streams': [],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/',
            'faultCode': errors.NOT_FOUND,
            }),
        ('store_duplicate', {
            'bundle_streams': [],
            'bundles': [('/anonymous/', 'test1.json', '{"foobar": 5}')],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/',
            'faultCode': errors.CONFLICT,
            }),
        ]

    bundles = []

    def test_put_failure(self):
        with contextlib.nested(
                fixtures.created_bundle_streams(self.bundle_streams),
                fixtures.created_bundles(self.bundles)):
            try:
                self.xml_rpc_call("put", self.content, self.content_filename,
                        self.pathname)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, self.faultCode)
            else:
                self.fail("Should have raised an exception")


class DashboardAPIPutFailureTransactionTests(TransactionTestCase):

    _bundle_streams = [{}]
    _content = '"unterminated string'
    _content_filename = 'bad.json'
    _pathname =  '/anonymous/'

    def setUp(self):
        self.endpoint_path = reverse("dashboard_app.dashboard_xml_rpc_handler")

    def xml_rpc_call(self, method, *args):
        request_body = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.client.post(self.endpoint_path,
                request_body, "text/xml")
        return xmlrpclib.loads(response.content)[0][0]

    def test_deserialize_failure_does_not_kill_the_bundle(self):
        # The test goes via the xml-rpc interface to use views
        # calling the put() API directly will never trigger out
        # transactions
        with fixtures.created_bundle_streams(self._bundle_streams):
            self.xml_rpc_call("put", self._content, self._content_filename,
                    self._pathname)
            self.assertEqual(Bundle.objects.all().count(), 1)


class DjangoTestCaseWithScenarios(TestCase):

    scenarios = [
            ('a', {}),
            ('b', {}),
            ]

    def test_database_is_empty_at_start_of_test(self):
        self.assertEqual(BundleStream.objects.all().count(), 0)
        stream = BundleStream.objects.create(slug='')


class BundleStreamListViewAnonymousTest(DashboardViewsTestCase):

    _USER = "user"
    _GROUP = "group"
    _SLUG = "slug"

    scenarios = [
        ('empty', {
            'bundle_streams': [],
        }),
        ('public_streams', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': _SLUG},],
        }),
        ('private_streams', {
            'bundle_streams': [
                {'slug': '', 'user': _USER},
                {'slug': _SLUG, 'user': _USER},],
        }),
        ('team_streams', {
            'bundle_streams': [
                {'slug': '', 'group': _GROUP},
                {'slug': _SLUG, 'group': _GROUP},],
        }),
        ('various_streams', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': _SLUG},
                {'slug': '', 'user': _USER},
                {'slug': _SLUG, 'user': _USER},
                {'slug': '', 'group': _GROUP},
                {'slug': _SLUG, 'group': _GROUP},
            ],
        }),
    ]

    def setUp(self):
        super(BundleStreamListViewAnonymousTest, self).setUp()
        self.user = None

    def test_status_code(self):
        response = self.client.get("/streams/")
        self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        response = self.client.get("/streams/")
        self.assertTemplateUsed(response,
                "dashboard_app/bundle_stream_list.html")

    def test_listed_bundles_are_the_ones_we_should_see(self):
        with fixtures.created_bundle_streams(self.bundle_streams) as bundle_streams:
            response = self.client.get("/streams/")
            expected_bsl = sorted(
                    [bundle_stream.pk for bundle_stream in
                        bundle_streams if
                        bundle_stream.can_access(self.user)])
            effective_bsl = sorted(
                    [bundle_stream.pk for bundle_stream in
                        response.context['bundle_stream_list']])
            self.assertEqual(effective_bsl, expected_bsl)


class BundleStreamListViewAuthorizedTest(BundleStreamListViewAnonymousTest):

    def setUp(self):
        super(BundleStreamListViewAuthorizedTest, self).setUp()
        self.client = TestClient()
        self.user = User.objects.create(username=self._USER)
        self.user.groups.create(name=self._GROUP)
        self.client.login_user(self.user)


class BundleStreamDetailViewAnonymousTest(DashboardViewsTestCase):

    _USER = "user"
    _GROUP = "group"
    _SLUG = "slug"

    scenarios = [
        ('public_stream', {'slug': ''}),
        ('public_named_stream', {'slug': _SLUG}),
        ('private_stream', {'slug': '', 'user': _USER}),
        ('private_named_stream', {'slug': _SLUG, 'user': _USER}),
        ('team_stream', {'slug': '', 'group': _GROUP}),
        ('team_named_stream', {'slug': _SLUG, 'group': _GROUP})
    ]

    def setUp(self):
        super(BundleStreamDetailViewAnonymousTest, self).setUp()
        self.bundle_stream = fixtures.make_bundle_stream(dict(
            slug=self.slug,
            user=getattr(self, 'user', ''),
            group=getattr(self, 'group', '')))
        self.user = None

    def test_status_code(self):
        response = self.client.get("/streams" + self.bundle_stream.pathname)
        if self.bundle_stream.can_access(self.user):
            self.assertEqual(response.status_code, 200)
        else:
            self.assertEqual(response.status_code, 403)

    def test_template_used(self):
        response = self.client.get("/streams" + self.bundle_stream.pathname)
        if self.bundle_stream.can_access(self.user):
            self.assertTemplateUsed(response,
                "dashboard_app/bundle_stream_detail.html")
        else:
            self.assertTemplateUsed(response,
                "403.html")


class BundleStreamDetailViewAuthorizedTest(BundleStreamDetailViewAnonymousTest):

    def setUp(self):
        super(BundleStreamDetailViewAuthorizedTest, self).setUp()
        self.client = TestClient()
        self.user = User.objects.get_or_create(username=self._USER)[0]
        self.group = Group.objects.get_or_create(name=self._GROUP)[0]
        self.user.groups.add(self.group)
        self.client.login_user(self.user)


class ModelWithAttachments(models.Model):
    """
    Test model that uses attachments
    """
    attachments = generic.GenericRelation(Attachment)

    class Meta:
        app_label = "dashboard_app"


class AttachmentTestCase(TestCase):
    _CONTENT = "text"
    _FILENAME = "filename"

    def setUp(self):
        self.obj = ModelWithAttachments.objects.create()

    def tearDown(self):
        self.obj.attachments.all().delete()

    def test_attachment_can_be_added_to_models(self):
        attachment = self.obj.attachments.create(
            content_filename = self._FILENAME, content=None)
        self.assertEqual(attachment.content_object, self.obj)

    def test_attachment_can_be_accessed_via_model(self):
        self.obj.attachments.create(
            content_filename = self._FILENAME, content=None)
        self.assertEqual(self.obj.attachments.count(), 1)
        retrieved_attachment = self.obj.attachments.all()[0]
        self.assertEqual(retrieved_attachment.content_object, self.obj)

    def test_attachment_stores_data(self):
        attachment = self.obj.attachments.create(
            content_filename = self._FILENAME, content=None)
        attachment.content.save(
            self._FILENAME,
            ContentFile(self._CONTENT))
        self.assertEqual(attachment.content_filename, self._FILENAME)
        attachment.content.open()
        try:
            self.assertEqual(attachment.content.read(), self._CONTENT)
        finally:
            attachment.content.close()


class CSRFConfigurationTestCase(CSRFTestCase):

    def setUp(self):
        super(CSRFConfigurationTestCase, self).setUp()
        self.login_path = reverse("django.contrib.auth.views.login")

    def test_csrf_token_present_in_login_page(self):
        import django
        if django.VERSION[:2] == (1, 1):
            # This feature is not supported on django 1.1
            return
        response = self.client.get(self.login_path)
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_cross_site_login_fails(self):
        import django
        if django.VERSION[:2] == (1, 1):
            # This feature is not supported on django 1.1
            return
        response = self.client.post(self.login_path, {
            'user': 'user', 'pass': 'pass'})
        self.assertEquals(response.status_code, 403)

    def test_csrf_not_protecting_xml_rpc_views(self):
        """call version and check that we didn't get 403"""
        endpoint_path = reverse("xml-rpc")
        request_body = xmlrpclib.dumps((), methodname="version")
        response = self.client.post(endpoint_path, request_body, "text/xml")
        self.assertContains(response, "<methodResponse>", status_code=200)


class TestUnicodeMethods(TestCase):


    def test_named_attribute(self):
        obj = NamedAttribute(name="name", value="value")
        self.assertEqual(unicode(obj), u"name: value")

    def test_bundle_stream(self):
        obj = BundleStream(pathname="/something/")
        self.assertEqual(unicode(obj), "/something/")

    def test_bundle(self):
        obj = Bundle(content_filename="file.json", pk=1)
        self.assertEqual(unicode(obj), u"Bundle 1 (file.json)")

    def test_bundle_deserialization_error(self):
        obj = BundleDeserializationError(error_message="boom")
        self.assertEqual(unicode(obj), u"boom")

    def test_test_with_id(self):
        """Test.test_id used when Test.name is not set"""
        obj = Test(test_id="org.some_test")
        self.assertEqual(unicode(obj), "org.some_test")

    def test_test_with_name(self):
        """Test.name used when available"""
        obj = Test(name="Some Test")
        self.assertEqual(unicode(obj), "Some Test")

    def test_test_with_id_and_name(self):
        """Test.name takes precedence over Test.test_id"""
        obj = Test(name="Some Test", test_id="org.some_test")
        self.assertEqual(unicode(obj), "Some Test")

    def test_test_run(self):
        obj = TestRun(analyzer_assigned_uuid="0" * 16)
        self.assertEqual(unicode(obj), "0" * 16)

    def test_attachment(self):
        obj = Attachment(content_filename="test.json")
        self.assertEqual(unicode(obj), "test.json")

    def test_test_result__pass(self):
        obj = TestResult(result=TestResult.RESULT_PASS, id=1)
        self.assertEqual(unicode(obj), "#1 pass")
    
    def test_test_result__fail(self):
        obj = TestResult(result=TestResult.RESULT_FAIL, id=1)
        self.assertEqual(unicode(obj), "#1 fail")
    
    def test_test_result__skip(self):
        obj = TestResult(result=TestResult.RESULT_SKIP, id=1)
        self.assertEqual(unicode(obj), "#1 skip")
    
    def test_test_result__unknown(self):
        obj = TestResult(result=TestResult.RESULT_UNKNOWN, id=1)
        self.assertEqual(unicode(obj), "#1 unknown")
