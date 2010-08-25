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
            'launch_control.utils.json.decoder',
            'launch_control.utils.json.encoder',
            'launch_control.utils.json.impl',
            'launch_control.utils.json.interface',
            'launch_control.utils.json.pod',
            'launch_control.utils.json.proxies',
            'launch_control.utils.json.proxies.datetime',
            'launch_control.utils.json.proxies.decimal',
            'launch_control.utils.json.proxies.timedelta',
            'launch_control.utils.json.proxies.uuid',
            'launch_control.utils.json.registry',
            'launch_control.utils.registry',
            'launch_control.utils_json',
            'launch_control.commands',
            'launch_control.commands.dispatcher',
            'launch_control.commands.interface',
            'launch_control.commands.misc',
            ]

def test_modules():
    return ['launch_control.tests.test_sample',
            'launch_control.tests.test_sw_profile',
            'launch_control.tests.test_utils_json',
            'launch_control.tests.test_utils_json_package',
            'launch_control.tests.test_utils_filesystem',
            'launch_control.tests.test_registry',
            'launch_control.tests.test_commands',
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
