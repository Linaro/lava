#!/usr/bin/env python
"""
Test cases for launch_control.sample module
"""

import launch_control.sample
from launch_control.sample import QualitativeSample


from unittest import TestCase

# Hack, see DocTestAwareTestLoader for insight
__doctest_module__ = launch_control.sample


class QualitativeSampleClassProperties(TestCase):
    """"Check for properties of QualitativeSample class"""
    def test_TEST_RESULT_PASS_is_pass(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_PASS, 'pass')
    def test_TEST_RESULT_FAIL_is_fail(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_FAIL, 'fail')


class QualitativeSampleManipulation(TestCase):
    """Check for properties of QualitativeSample instances"""
    def setUp(self):
        self.sample = QualitativeSample(
                QualitativeSample.TEST_RESULT_PASS, 'org.example.test')
    def test_test_id_set_ok(self):
        self.assertEqual(self.sample.test_id, 'org.example.test')
    def test_test_result_set_ok(self):
        self.assertEqual(self.sample.test_result,
                QualitativeSample.TEST_RESULT_PASS)
    def test_test_id_validation(self):
        self.assertRaises(ValueError, self.sample._set_test_id,
                'something that does not look like a domain name')
    def test_test_result_can_be_set_to_pass(self):
        self.sample.test_result = 'pass'
        self.assertEqual(self.sample.test_result, 'pass')
    def test_test_result_can_be_set_to_fail(self):
        self.sample.test_result = 'fail'
        self.assertEqual(self.sample.test_result, 'fail')
