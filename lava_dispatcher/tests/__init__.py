import unittest

def test_suite():
    module_names = [
        'lava_dispatcher.tests.test_config',
        'lava_dispatcher.tests.test_context',
        'lava_dispatcher.tests.test_client',
    ]
    loader = unittest.TestLoader()
    return loader.loadTestsFromNames(module_names)
