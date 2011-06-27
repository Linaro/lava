import unittest

def test_suite():
    module_names = ['lava_dispatcher.tests.test_config',]
    loader = unittest.TestLoader()
    return loader.loadTestsFromNames(module_names)
