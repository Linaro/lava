"""
Module that tests the behaviour of the json package with mocked
imports. It was separated to isolate side effects that otherwise
complicate regular tests
"""
from launch_control.thirdparty.mocker import Mocker
from launch_control.utils.import_prohibitor import (
        ImportMockingTestCase,)

# This is here to protect this module from being reloaded after import
# mocking takes place in one of the tests below. This marker is required
# because import mocking reloads all modules that depend on a module
# being prohibited to make side effects happen (such as ImportError
# being raised and alternate code-paths being taken).
__inhibit_protect__ = True


class IJSONSupportTestCase(ImportMockingTestCase):

    def test_json_import_failure(self):
        """ Make sure we import simplejson if json is not available """
        self.prohibit_importing('json')
        self.mock_imports()
        mocker = Mocker()
        obj = mocker.replace('simplejson')
        mocker.replay()
        # Needs explicit reimport after import mocking
        import launch_control.utils.json as imported_module
        self.assertTrue(imported_module.json is obj)
        mocker.verify()
        mocker.restore()
