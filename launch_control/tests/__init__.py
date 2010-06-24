"""
Package with unit tests for launch_control
"""
import doctest
import unittest

def test_suite():
    """
    Build an unittest.TestSuite() object with all the tests in _modules.
    Each module is harvested for both regular unittests and doctests
    """
    modules = (
            # Docstring tests for helper test code:
            'launch_control.testing.call_helper',
            # Dedicated unit tests
            'launch_control.tests.sample',
            'launch_control.tests.sw_profile',
            # Docstring tests:
            'launch_control.sw_profile',
            'launch_control.utils_json',
            'launch_control.sample')

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for name in modules:
        unit_suite = loader.loadTestsFromName(name)
        suite.addTests(unit_suite)
        doc_suite = doctest.DocTestSuite(name)
        suite.addTests(doc_suite)
    return suite
