# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Dashboard
#
# Lava Dashboard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Dashboard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

"""
XMP-RPC API
"""

import logging
from linaro_django_xmlrpc.models import (
    ExposedAPI,
    Mapper,
    xml_rpc_signature,
)


class errors:
    """
    A namespace for error codes that may be returned by various XML-RPC
    methods. Where applicable existing status codes from HTTP protocol
    are reused
    """
    AUTH_FAILED = 100
    AUTH_BLOCKED = 101
    BAD_REQUEST = 400
    AUTH_REQUIRED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501


class DashboardAPI(ExposedAPI):
    """
    Dashboard API object.

    All public methods are automatically exposed as XML-RPC methods
    """

    def __init__(self, context=None):
        super(DashboardAPI, self).__init__(context)
        self.logger = logging.getLogger(__name__ + 'DashboardAPI')

    @xml_rpc_signature('str')
    def version(self):
        """
        Name
        ----
        `version` ()

        Deprecated
        ----------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return 'unknown'

    @xml_rpc_signature('str', 'str', 'str', 'str')
    def put(self, content, content_filename, pathname):
        """
        Name
        ----
        `put` (`content`, `content_filename`, `pathname`)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return ""

    @xml_rpc_signature('str', 'str', 'str', 'str')
    def put_ex(self, content, content_filename, pathname):
        """
        Name
        ----
        `put` (`content`, `content_filename`, `pathname`)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return ""

    def put_pending(self, content, pathname, group_name):
        """
        Name
        ----
        `put_pending` (`content`, `pathname`, `group_name`)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return ""

    def put_group(self, content, content_filename, pathname, group_name):
        """
        Name
        ----
        `put_group` (`content`, `content_filename`, `pathname`, `group_name`)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return ""

    def get(self, content_sha1):
        """
        Name
        ----
        `get` (`content_sha1`)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return {"content": "",
                "content_filename": ""}

    @xml_rpc_signature('struct')
    def streams(self):
        """
        Name
        ----
        `streams` ()

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return []

    def bundles(self, pathname):
        """
        Name
        ----
        `bundles` (`pathname`)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        bundles = []
        return bundles

    @xml_rpc_signature('str')
    def get_test_names(self, device_type=None):
        """
        Name
        ----
        `get_test_names` ([`device_type`]])

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return []

    def deserialize(self, content_sha1):
        """
        Name
        ----
        `deserialize` (`content_sha1`)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return False

    def make_stream(self, pathname, name):
        """
        Name
        ----
        `make_stream` (`pathname`, `name`)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return ""

    def get_filter_results(self, filter_name, count=10, offset=0):
        """
        Name
        ----
         ::

          get_filter_results(filter_name, count=10, offset=0)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return []

    def get_filter_results_since(self, filter_name, since=None):
        """
        Name
        ----
         ::

          get_filter_results_since(filter_name, since=None)

        Removal of V1 support
        --------------------
        This function has been disabled in api_version 2. It is
        retained as a stub for older versions of clients. Please
        update your tool to use LAVA V2.

        See system.api_version()
        """
        return []


# Mapper used by the legacy URL
legacy_mapper = Mapper()
legacy_mapper.register_introspection_methods()
legacy_mapper.register(DashboardAPI, '')
