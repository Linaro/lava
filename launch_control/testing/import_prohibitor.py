"""
Helper module with ImportMockingTestCase class
"""

import sys
import gc
import types

from unittest import TestCase


class _ImportProhibitorHook(object):
    def __init__(self):
        self.prohibited = set()
    def disallow(self, fullname):
        self.prohibited.add(fullname)
    def find_module(self, fullname, path=None):
        if fullname in self.prohibited:
            return self
    def load_module(self, fullname):
        raise ImportError("Importing module %s is prohibited" % (fullname,))


class ImportMockingTestCase(TestCase):
    def setUp(self):
        super(ImportMockingTestCase, self).setUp()
        self._hook = _ImportProhibitorHook()
        self._hidden_modules = {}

    def tearDown(self):
        self._restore_hidden()
        super(ImportMockingTestCase, self).tearDown()

    def prohibit_importing(self, fullname):
        """
        Disallow importing of module `fullname'.
        During the rest of the test case any attempts to import
        this module will raise ImportError.
        """
        self._hook.disallow(fullname)

    def _get_referring_modules(self, obj):
        """
        Find all modules that *directly* refer to object `obj'
        """
        for ref_obj in gc.get_referrers(obj):
            if isinstance(ref_obj, dict) and '__name__' in ref_obj:
                for mod in gc.get_referrers(ref_obj):
                    if isinstance(mod, types.ModuleType):
                        yield mod.__name__

    def mock_imports(self):
        """
        Make prohibit_importing() work by hiding and importing
        again all the modules that depended on an imported
        prohibited module.

        This does _NOT_ work 100% reliably as it only finds modules that
        directly imported one of the prohibited modules AND it depends
        on being able to safely reimport them.

        The side effects of this function last until the end of the test
        case, in other words, until tearDown() is implicitly called.
        """
        to_reload = set()
        to_hide = set(self._hook.prohibited)

        # For all the things we want to disallow
        for fullname in self._hook.prohibited:
            # Modules not yet loaded do not require any actions
            if fullname not in sys.modules:
                continue
            # Loaded modules must be hidden
            to_hide.add(fullname)
            # And all of their dependencies must be reloaded
            module = sys.modules[fullname]
            for related_fullname in self._get_referring_modules(module):
                if hasattr(sys.modules[related_fullname],
                        '__inhibit_protect__'):
                    continue
                to_hide.add(related_fullname)
                to_reload.add(related_fullname)
        # Install our meta-import hook
        sys.meta_path.append(self._hook)
        # Hide modules
        for fullname in to_hide:
            self._hide(fullname)
        # Reload modules 
        for fullname in to_reload:
            self._reload(fullname)

    def _hide(self, fullname):
        self._hidden_modules[fullname] = sys.modules[fullname]
        del sys.modules[fullname]

    def _reload(self, fullname):
        assert fullname not in sys.modules
        __import__(fullname, fromlist=[''])

    def _restore_hidden(self):
        if self._hook in sys.meta_path:
            sys.meta_path.remove(self._hook)
        sys.modules.update(self._hidden_modules)
