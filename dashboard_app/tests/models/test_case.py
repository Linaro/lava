"""
Test for the TestCase model
"""

from django.db import IntegrityError
from django.test import TestCase
from django_testscenarios.ubertest import TestCaseWithScenarios

from dashboard_app.models import (
    Test,
    TestCase as TestCaseModel,
)


class TestCaseConstructionTests(TestCaseWithScenarios):

    scenarios = [
        ('simple1', {
            'test_id': 'org.linaro.testheads.android',
            'test_case_id': 'testcase1',
            'name': "Boot test",
            'units': '',
        }),
        ('simple2', {
            'test_id': 'org.mozilla.unit-tests',
            'test_case_id': 'testcase125',
            'name': "Rendering test",
            'units': 'frames/s',
        }),
    ]

    def setUp(self):
        super(TestCaseConstructionTests, self).setUp()
        self.test = Test(test_id=self.test_id)
        self.test.save()

    def test_construction(self):
        test_case = TestCaseModel(
            test = self.test,
            test_case_id = self.test_case_id,
            name = self.name,
            units = self.units
        )
        test_case.save()
        self.assertEqual(self.name, test_case.name)
        self.assertEqual(self.test_case_id, test_case.test_case_id)
        self.assertEqual(self.name, test_case.name)
        self.assertEqual(self.units, test_case.units)

    def test_test_and_test_case_id_uniqueness(self):
        test_case = TestCaseModel(
            test = self.test,
            test_case_id = self.test_case_id)
        test_case.save()
        test_case2 = TestCaseModel(
            test = self.test,
            test_case_id = self.test_case_id)
        self.assertRaises(IntegrityError, test_case2.save)


class TestCaseUnicodeTests(TestCase):

    def test_test_case_with_id(self):
        """TestCase.test_case_id used when TestCase.name is not set"""
        obj = TestCaseModel(test_case_id="test123")
        self.assertEqual(unicode(obj), "test123")

    def test_test_case_with_name(self):
        """TestCase.name used when available"""
        obj = TestCaseModel(name="Test 123")
        self.assertEqual(unicode(obj), "Test 123")

    def test_test_case_with_id_and_name(self):
        """TestCase.name takes precedence over TestCase.test_case_id"""
        obj = TestCaseModel(name="Test 123", test_case_id="test123")
        self.assertEqual(unicode(obj), "Test 123")
