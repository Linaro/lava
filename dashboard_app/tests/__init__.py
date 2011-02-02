"""
Package with all tests for dashboard_app
"""

import unittest

TEST_MODULES = [
    'models.attachment',
    'models.bundle',
    'models.bundle_deserialization_error',
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
    'other.login',
    'other.test_client',
    'other.xml_rpc',
    'regressions.LP658917',
    'views.bundle_stream_list_view',
    'views.test_run_detail_view',
    'views.test_run_list_view',
    'views.xml_rpc_handler',
]

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
            import logging
            logging.exception("Unable to import test module %s", module_name)
            raise
        else:
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                    _locals[attr] = obj

load_tests_from_submodules(locals())
