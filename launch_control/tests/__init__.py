"""
Package with unit tests for launch_control
"""
import doctest
import unittest


_modules = (
        # Docstring tests for helper test code:
        'launch_control.testing.call_helper',
        # Dedicated unit tests
        'launch_control.tests.sample',
        # Docstring tests:
        'launch_control.utils_json',
        'launch_control.sample')


def _import(name):
    """
    Wrapper for __import__() that works as most people intend to use
    __import__().  To understand why it's needed consider the following
    example. Let's say wa want to import xml.dom:
    >>> __import__('xml.dom')
    <module 'xml' from ...>

    We've got xml instead, that has to be wrong.  Apparently this is the
    way __import__() is supposed to work, as explained in the
    documentation. What we actually wanted is this:
    >>> import xml.dom
    >>> xml.dom
    <module 'xml.dom' from ...>

    To get the right behavior we need to use non-empty 'fromlist'
    argument, like this:
    >>> __import__('xml.dom', fromlist=[''])
    <module 'xml.dom' from ...>

    And this is exactly what _import() does:
    >>> _import('xml.dom')
    <module 'xml.dom' from ...>
    """
    return __import__(name, fromlist=[''])


def _get_all_tests():
    """
    Build an unittest.TestSuite() object with all the tests in _modules.
    Each module is harvested for both regular unittests and doctests
    """
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for name in _modules:
        module = _import(name)
        unit_suite = loader.loadTestsFromModule(module)
        if unit_suite and unit_suite.countTestCases() > 0:
            suite.addTest(unit_suite)
        doc_suite = doctest.DocTestSuite(module)
        if doc_suite and doc_suite.countTestCases() > 0:
            suite.addTest(doc_suite)
    return suite

def test_all():
    return _get_all_tests()
