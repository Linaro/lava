"""
XMP-RPC API
"""

import xmlrpclib

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.db.models import Q

from launch_control.dashboard_app import __version__ as dashboard_version
from launch_control.dashboard_app.dispatcher import xml_rpc_signature

from launch_control.dashboard_app.models import (
        Bundle,
        BundleStream,
        )


class errors:
    """
    A namespace for error codes that may be returned by various XML-RPC
    methods. Where applicable existing status codes from HTTP protocol
    are reused
    """
    AUTH_FAILED = 100
    AUTH_BLOCKED = 101
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501


class DashboardAPI(object):
    """
    Dashboard API object.

    All public methods are automatically exposed as XML-RPC methods
    """

    @xml_rpc_signature('str')
    def version(self):
        """
        Name
        ----
        `version` ()

        Description
        -----------
        Return dashboard server version. The version is a string with
        dots separating five components.

        The components are:
            1. major version
            2. minor version
            3. micro version
            4. release level
            5. serial

        See: http://docs.python.org/library/sys.html#sys.version_info

        Returns value
        -------------
        Server version string
        """
        return ".".join(map(str, dashboard_version))

    @xml_rpc_signature('str', 'str', 'str', 'str')
    def put(self, content, content_filename, pathname):
        """
        Name
        ----
        `put` (`content`, `content_filename`, `pathname`)

        Description
        -----------
        Upload a bundle to the server.

        Arguments
        ---------
        `content`: string
            Full text of the bundle. This *SHOULD* be a valid JSON
            document and it *SHOULD* match the "Dashboard Bundle Format
            1.0" schema. The SHA1 of the content *MUST* be unique or a
            ``Fault(409, "...")`` is raised. This is used to protect
            from simple duplicate submissions.
        `content_filename`: string
            Name of the file that contained the text of the bundle. The
            `content_filename` can be an arbitrary string and will be
            stored along with the content for reference.
        `pathname`: string
            Pathname of the bundle stream where a new bundle should
            be created and stored. This argument *MUST* designate a
            pre-existing bundle stream or a ``Fault(404, "...")`` exception
            is raised. In addition the user *MUST* have access
            permission to upload bundles there or a ``Fault(403, "...")``
            exception is raised. See below for access rules.

        Return value
        ------------
        If all goes well this function returns the SHA1 of the content.

        Exceptions raised
        -----------------
        404
            Bundle stream not found
        409
            Duplicate bundle content
        403
            Uploading to specified stream is not permitted

        Rules for bundle stream access
        ------------------------------
        The following rules govern bundle stream upload access rights:
            - all anonymous streams are accessible
            - personal streams are accessible by owners
            - team streams are accessible by team members

        """
        user = None
        try:
            bundle_stream = BundleStream.objects.get(pathname=pathname)
        except BundleStream.DoesNotExist:
            raise xmlrpclib.Fault(errors.NOT_FOUND,
                    "Bundle stream not found")
        if not bundle_stream.can_upload(user):
            raise xmlrpclib.Fault(errors.FORBIDDEN,
                    "Uploading to specified stream is not permitted")
        try:
            bundle = Bundle.objects.create(
                    bundle_stream=bundle_stream,
                    uploaded_by=user,
                    content_filename=content_filename)
            bundle.save()
            bundle.content.save("bundle-{0}".format(bundle.pk),
                    ContentFile(content))
            bundle.save()
        except IntegrityError:
            bundle.delete()
            raise xmlrpclib.Fault(errors.CONFLICT,
                    "Duplicate bundle content")
        return bundle.content_sha1

    def get(self, content_sha1):
        """
        Name
        ----
        `get` (`content_sha1`)

        Description
        -----------
        Download a bundle from the server.

        Arguments
        ---------
        `content_sha1`: string
            SHA1 hash of the content of the bundle to download. This
            *MUST* designate an bundle or ``Fault(404, "...")`` is raised.

        Return value
        ------------
        This function returns an XML-RPC struct with the following fields:

        `content_filename`: string
            The value that was stored on a previous call to put()
        `content`: string
            The full text of the bundle

        Exceptions raised
        -----------------
        404
            Bundle not found
        403
            Downloading from the stream that contains this bundle is
            not permitted

        Rules for bundle stream access
        ------------------------------
        The following rules govern bundle stream download access rights:
            - all anonymous streams are accessible
            - personal streams are accessible by owners
            - team streams are accessible by team members
        """
        user = None
        try:
            bundle = Bundle.objects.get(content_sha1=content_sha1)
        except Bundle.DoesNotExist:
            raise xmlrpclib.Fault(errors.NOT_FOUND,
                    "Bundle not found")
        if not bundle.bundle_stream.can_download(user):
            raise xmlrpclib.Fault(errors.FORBIDDEN,
                    "Downloading from specified stream is not permitted")
        else:
            return {"content": bundle.content.read(),
                    "content_filename": bundle.content_filename}

    @xml_rpc_signature('struct')
    def streams(self):
        """
        Name
        ----
        `streams` ()

        Description
        -----------
        List all bundle streams that the user has access to

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array of XML-RPC structs with
        the following fields:

        `pathname`: string
            The pathname of the bundle stream
        `name`: string
            The user-configurable name of the bundle stream
        `user`: string
            The username of the owner of the bundle stream for personal
            streams or an empty string for public and team streams.
        `group`: string
            The name of the team that owsn the bundle stream for team
            streams or an empty string for public and personal streams.
        `bundle_count`: int
            Number of bundles that are in this stream

        Exceptions raised
        -----------------
        None

        Rules for bundle stream access
        ------------------------------
        The following rules govern bundle stream download access rights:
            - all anonymous streams are accessible
            - personal streams are accessible by owners
            - team streams are accessible by team members
        """
        user = None
        if user is not None:
            bundle_streams = BundleStream.objects.filter(
                    Q(user__isnull = True, group__isnull = True) |
                    Q(user = user) |
                    Q(group__in = request.user.groups.all()))
        else:
            bundle_streams = BundleStream.objects.filter(
                    user__isnull = True, group__isnull = True)
        return [{
            'pathname': bundle_stream.pathname,
            'name': bundle_stream.name,
            'user': bundle_stream.user.username if bundle_stream.user else "",
            'group': bundle_stream.group.name if bundle_stream.group else "",
            'bundle_count': bundle_stream.bundles.count(),
            } for bundle_stream in bundle_streams]

    def bundles(self, pathname):
        """
        Name
        ----
        `bundles` (`pathname`)

        Description
        -----------
        List all bundles in a specified bundle stream

        Arguments
        ---------
        `pathname`: string
            The pathname of the bundle stream to query. This argument
            *MUST* designate an existing stream or Fault(404, "...") is
            raised. The user *MUST* have access to this stream or
            Fault(403, "...") is raised.

        Return value
        ------------
        This function returns an XML-RPC array of XML-RPC structs with
        the following fields:

        `uploaded_by`: string
            The username of the user that uploaded this bundle or 
            empty string if this bundle was uploaded anonymously.
        `uploaded_on`: datetime
            The timestamp when the bundle was uploaded
        `content_filename`: string
            The filename of the original bundle file
        `content_sha1`: string
            The SHA1 hash if the content of the bundle
        `is_deserialized`: bool
            True if the bundle was de-serialized successfully, false otherwise

        Exceptions raised
        -----------------
        404
            Bundle stream not found
        403
            Listing bundles in this bundle stream is not permitted

        Rules for bundle stream access
        ------------------------------
        The following rules govern bundle stream download access rights:
            - all anonymous streams are accessible
            - personal streams are accessible by owners
            - team streams are accessible by team members
        """
        user = None
        bundles = Bundle.objects.filter(
                bundle_stream__pathname = pathname)
        return [{
            'uploaded_by': bundle.uploaded_by.username if bundle.uploaded_by else "",
            'uploaded_on': bundle.uploaded_on,
            'content_filename': bundle.content_filename,
            'content_sha1': bundle.content_sha1,
            'is_deserialized': bundle.is_deserialized
            } for bundle in bundles]
