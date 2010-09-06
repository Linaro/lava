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
        Return dashboard server version.
        """
        return ".".join(map(str, dashboard_version))

    def put(self, content, filename, pathname):
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
                    content_filename=filename)
            bundle.content.save(filename, ContentFile(content))
            bundle.save()
        except IntegrityError:
            bundle.delete()
            raise xmlrpclib.Fault(errors.CONFLICT,
                    "Duplicate bundle detected")
        return bundle.pk

    def get(self, bundle_id):
        user = None
        try:
            bundle = Bundle.objects.get(pk=bundle_id)
        except BundleStream.DoesNotExist:
            raise xmlrpclib.Fault(errors.NOT_FOUND,
                    "Bundle not found")
        if not bundle.bundle_stream.can_download(user):
            raise xmlrpclib.Fault(errors.FORBIDDEN,
                    "Downloading from specified stream is not permitted")
        else:
            return {"content": bundle.content.read(),
                    "content_filename": bundle.content_filename}

    def streams(self):
        user = None
        if user is not None:
            bundle_streams = BundleStream.objects.filter(
                    Q(user = user) | Q(group in user.groups))
        else:
            bundle_streams = BundleStream.objects.filter(
                    user = None, group = None)
        return [{
            'pathname': bundle_stream.pathname,
            'name': bundle_stream.name,
            'user': bundle_stream.user.username if bundle_stream.user else "",
            'group': bundle_stream.group.name if bundle_stream.group else "",
            'bundle_count': bundle_stream.bundles.count(),
            } for bundle_stream in bundle_streams]

    def bundles(self, pathname):
        user = None
        bundles = Bundle.objects.filter(
                bundle_stream__pathname = pathname)
        return [{
            'pk': bundle.pk,
            'uploaded_by': bundle.uploaded_by.username if bundle.uploaded_by else "",
            'uploaded_on': bundle.uploaded_on,
            'content_filename': bundle.content_filename,
            'content_sha1': bundle.content_sha1,
            'is_deserialized': bundle.is_deserialized
            } for bundle in bundles]
