"""
Package with all tests for dashboard_app
"""

import unittest

from testscenarios.scenarios import generate_scenarios

TEST_MODULES = [
    'models.hw_device',
    'models.sw_package',
    'models.test_case',
    'other.tests',
]

def suite():
    loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    for name in TEST_MODULES:
        tests = loader.loadTestsFromName('dashboard_app.tests.' + name)
        test_suite.addTests(generate_scenarios(tests))
    return test_suite
