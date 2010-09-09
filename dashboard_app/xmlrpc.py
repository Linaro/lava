"""
XMP-RPC API
"""

from dashboard_app import __version__ as dashboard_version
from dashboard_app.dispatcher import xml_rpc_signature


class DashboardAPI(object):
    """
    Dashboard API object.

    All public methods are automatically exposed as XML-RPC methods
    """

    @xml_rpc_signature('str')
    def version(self):
        """
        Return dashboard server version.
        """
        return ".".join(map(str, dashboard_version))
