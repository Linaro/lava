# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

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

    def mock_imports(self, reload_list=None):
        """
        Make prohibit_importing() work by hiding and importing
        again all the modules that depended on an imported
        prohibited module.

        This does _NOT_ work 100% reliably as it only finds modules that
        directly imported one of the prohibited modules AND it depends
        on being able to safely reimport them. If autodetection fails
        pass a module, or a list of modules to reimport.

        The side effects of this function last until the end of the test
        case, in other words, until tearDown() is implicitly called.
        """
        to_reload = set()
        if reload_list is not None:
            if isinstance(reload_list, basestring):
                reload_list = [reload_list]
            to_reload.update(reload_list)
        to_hide = set()
        to_hide.update(to_reload)

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
        # Only reload if it is not loaded already
        # This might seem crazy but it is required because
        # we reload a sequence of modules that might import
        # things themselves.
        # Example:
        #   1) to_reload: a, b; to_hide: a, b
        #      original a and b are now hidden
        #   2) _reload('a')
        #   3) we __import__('a')
        #   4) a imports b
        #   5) _reload('b')
        #   6) 'b' is already imported so we don't do anything about it
        if fullname not in sys.modules:
            __import__(fullname, fromlist=[''])

    def _restore_hidden(self):
        if self._hook in sys.meta_path:
            sys.meta_path.remove(self._hook)
        sys.modules.update(self._hidden_modules)
