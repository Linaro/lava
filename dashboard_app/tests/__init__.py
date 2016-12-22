"""
Package with all tests for dashboard_app
"""

import imp
import logging
import unittest


TEST_MODULES = [
    'models.test_bundle',
    'models.test_bundle_deserialization_error',
    'models.test_bundle_stream',
    'models.test_hw_device',
    'models.test_named_attribute',
    'models.test_sw_package',
    'models.test',
    'models.test_case',
    'models.test_result',
    'models.test_run',
    'other.test_csrf',
    'other.test_dashboard_api',
    'other.test_deserialization',
    'other.test_client',
    'regressions.test_LP658917',
    'views.test_bundle_stream_list_view',
    'views.test_run_detail_view',
    'views.test_run_list_view',
    'views.test_redirects',
]


try:
    imp.find_module('django_openid_auth')
    TEST_MODULES += ['other.test_login']
except ImportError:
    pass


def load_tests_from_submodules(_locals):
    """
    Load all test classes from sub-modules as if they were here locally.

    This makes django test dispatcher work correctly and allows users to
    use the optional test identifier. The identifier has this format:
        Application.TestClass[.test_method]
    """
    for name in TEST_MODULES:
        module_name = 'dashboard_app.tests.' + name
        try:
            module = __import__(module_name, fromlist=[''])
        except ImportError:
            logging.exception("Unable to import test module %s", module_name)
            raise
        else:
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                    _locals[attr] = obj


load_tests_from_submodules(locals())
