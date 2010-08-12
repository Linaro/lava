"""
Package with unit tests for launch_control
"""
import doctest
import unittest

def app_modules():
    return ['launch_control.sample',
            'launch_control.sw_profile',
            'launch_control.utils.call_helper',
            'launch_control.utils.filesystem',
            'launch_control.utils.import_prohibitor',
            'launch_control.utils.json',
            'launch_control.utils_json',
            ]

def test_modules():
    return ['launch_control.tests.test_sample',
            'launch_control.tests.test_sw_profile',
            'launch_control.tests.test_utils_json',
            'launch_control.tests.test_utils_json_package',
            'launch_control.tests.test_utils_filesystem',
            ]

def test_suite():
    """
    Build an unittest.TestSuite() object with all the tests in _modules.
    Each module is harvested for both regular unittests and doctests
    """
    modules = app_modules() + test_modules()
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for name in modules:
        unit_suite = loader.loadTestsFromName(name)
        suite.addTests(unit_suite)
        doc_suite = doctest.DocTestSuite(name)
        suite.addTests(doc_suite)
    return suite
