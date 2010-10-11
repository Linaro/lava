"""
Package with all tests for dashboard_app
"""

import unittest

from testscenarios.scenarios import generate_scenarios

TEST_MODULES = [
    'models.attachment',
    'models.bundle',
    'models.bundle_stream',
    'models.hw_device',
    'models.named_attribute',
    'models.sw_package',
    'models.test',
    'models.test_case',
    'models.test_result',
    'models.test_run',
    'other.csrf',
    'other.dashboard_api',
    'other.deserialization',
    'other.test_client',
    'other.tests',
]

def suite():
    loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    for name in TEST_MODULES:
        tests = loader.loadTestsFromName('dashboard_app.tests.' + name)
        test_suite.addTests(generate_scenarios(tests))
    return test_suite
