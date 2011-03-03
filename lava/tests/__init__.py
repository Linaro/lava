import unittest

def test_suite():
    module_names = ['lava.tests.test_config',]
    loader = unittest.TestLoader()
    return loader.loadTestsFromNames(module_names)
