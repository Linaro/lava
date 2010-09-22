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
Module with some interface for a degree of portability between different
JSON implementations available with different python versions.
"""
import os

# Temporary workaround, unit tests in other module will break import
# json below (inhibit protect prevents this module from being reloaded)
__inhibit_protect__ = True

def _get_json_impl():
    """
    Get available JSON implementation

    XXX: This is quite annoying as there _are_ differences between them
    that break unit tests on python2.5 vs 2.6 vs 2.7. Consider dropping
    one good JSON library as bundled dependency since this is such a
    core feature it should not break randomly.
    """
    impl = os.getenv("JSON_IMPL", "auto")
    if impl == "auto":
        try:
            import json
        except ImportError:
            import simplejson as json
    elif impl == "json":
        import json
    elif impl == "simplejson":
        import simplejson as json
    else:
        raise ImportError("Environment variable JSON_IMPL must be one of 'auto', 'json', 'simplejson'")
    return json

json = _get_json_impl()
