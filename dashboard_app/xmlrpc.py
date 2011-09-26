# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
XMP-RPC API
"""

import decimal
import logging
import xmlrpclib

from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django.db import IntegrityError, DatabaseError
from linaro_django_xmlrpc.models import (
    ExposedAPI,
    Mapper,
    xml_rpc_signature,
)

from dashboard_app import __version__
from dashboard_app.models import (
    Bundle,
    BundleStream,
    DataView,
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


class DashboardAPI(ExposedAPI):
    """
    Dashboard API object.

    All public methods are automatically exposed as XML-RPC methods
    """

    data_view_connection = DataView.get_connection()

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

        Return value
        -------------
        Server version string
        """
        return ".".join(map(str, __version__))

    def _put(self, content, content_filename, pathname):
        try:
            logging.debug("Getting bundle stream")
            bundle_stream = BundleStream.objects.accessible_by_principal(self.user).get(pathname=pathname)
        except BundleStream.DoesNotExist:
            logging.debug("Bundle stream does not exists, aborting")
            raise xmlrpclib.Fault(errors.NOT_FOUND,
                    "Bundle stream not found")
        try:
            logging.debug("Creating bundle object")
            bundle = Bundle.objects.create_with_content(bundle_stream, self.user, content_filename, content)
        except (IntegrityError, ValueError) as exc:
            logging.debug("Raising xmlrpclib.Fault(errors.CONFLICT)")
            raise xmlrpclib.Fault(errors.CONFLICT, str(exc))
        except:
            logging.exception("big oops")
            raise
        else:   
            logging.debug("Deserializing bundle")
            bundle.deserialize()
            return bundle

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
            Either:

                - Bundle stream not found
                - Uploading to specified stream is not permitted
        409
            Duplicate bundle content

        Rules for bundle stream access
        ------------------------------
        The following rules govern bundle stream upload access rights:
            - all anonymous streams are accessible
            - personal streams are accessible to owners
            - team streams are accessible to team members

        """
        bundle = self._put(content, content_filename, pathname)
        logging.debug("Returning bundle SHA1")
        return bundle.content_sha1

    @xml_rpc_signature('str', 'str', 'str', 'str')
    def put_ex(self, content, content_filename, pathname):
        """
        Name
        ----
        `put` (`content`, `content_filename`, `pathname`)

        Description
        -----------
        Upload a bundle to the server.  A variant on put_ex that returns the
        URL of the bundle instead of its SHA1.

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
        If all goes well this function returns the full URL of the bundle.

        Exceptions raised
        -----------------
        404
            Either:

                - Bundle stream not found
                - Uploading to specified stream is not permitted
        409
            Duplicate bundle content

        Rules for bundle stream access
        ------------------------------
        The following rules govern bundle stream upload access rights:
            - all anonymous streams are accessible
            - personal streams are accessible to owners
            - team streams are accessible to team members

        """
        bundle = self._put(content, content_filename, pathname)
        logging.debug("Returning permalink to bundle")
        return self._context.request.build_absolute_uri(
            reverse(
                'dashboard_app.views.redirect_to_bundle',
                kwargs={'content_sha1':bundle.content_sha1}))

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
            Either:

                - Bundle not found
                - Downloading from the stream that contains this bundle is
                  not permitted

        Rules for bundle stream access
        ------------------------------
        The following rules govern bundle stream download access rights:
            - all anonymous streams are accessible
            - personal streams are accessible to owners
            - team streams are accessible to team members
        """
        try:
            bundle = Bundle.objects.get(content_sha1=content_sha1)
            if not bundle.bundle_stream.is_accessible_by(self.user):
                raise Bundle.DoesNotExist()
        except Bundle.DoesNotExist:
            raise xmlrpclib.Fault(errors.NOT_FOUND,
                    "Bundle not found")
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
            - personal streams are accessible to owners
            - team streams are accessible to team members
        """
        bundle_streams = BundleStream.objects.accessible_by_principal(self.user)
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
        `content_size`: int
            This element was added in server version 0.4
            The size of the content
        `is_deserialized`: bool
            True if the bundle was de-serialized successfully, false otherwise


        Exceptions raised
        -----------------
        404
            Either:

                - Bundle stream not found
                - Listing bundles in this bundle stream is not permitted

        Rules for bundle stream access
        ------------------------------
        The following rules govern bundle stream download access rights:
            - all anonymous streams are accessible
            - personal streams are accessible to owners
            - team streams are accessible to team members
        """
        try:
            bundle_stream = BundleStream.objects.accessible_by_principal(self.user).get(pathname=pathname)
        except BundleStream.DoesNotExist:
            raise xmlrpclib.Fault(errors.NOT_FOUND, "Bundle stream not found")
        return [{
            'uploaded_by': bundle.uploaded_by.username if bundle.uploaded_by else "",
            'uploaded_on': bundle.uploaded_on,
            'content_filename': bundle.content_filename,
            'content_sha1': bundle.content_sha1,
            'content_size': bundle.content.size,
            'is_deserialized': bundle.is_deserialized
            } for bundle in bundle_stream.bundles.all().order_by("uploaded_on")]


    def deserialize(self, content_sha1):
        """
        Name
        ----
        `deserialize` (`content_sha1`)

        Description
        -----------
        Deserialize bundle on the server

        Arguments
        ---------
        `content_sha1`: string
            SHA1 hash of the content of the bundle to download. This
            *MUST* designate an bundle or ``Fault(404, "...")`` is raised.

        Return value
        ------------
        True - deserialization okay
        False - deserialization not needed

        Exceptions raised
        -----------------
        404
            Bundle not found
        409
            Bundle import failed
        """
        try:
            bundle = Bundle.objects.get(content_sha1=content_sha1)
        except Bundle.DoesNotExist:
            raise xmlrpclib.Fault(errors.NOT_FOUND, "Bundle not found")
        if bundle.is_deserialized:
            return False
        bundle.deserialize()
        if bundle.is_deserialized is False:
            raise xmlrpclib.Fault(
                errors.CONFLICT,
                bundle.deserialization_error.error_message)
        return True

    def make_stream(self, pathname, name):
        """
        Name
        ----
        `make_stream` (`pathname`, `name`)

        Description
        -----------
        Create a bundle stream with the specified pathname 

        Arguments
        ---------
        `pathname`: string
            The pathname must refer to an anonymous stream
        `name`: string
            The name of the stream (free form description text)

        Return value
        ------------
        pathname is returned

        Exceptions raised
        -----------------
        403
            Pathname does not designate an anonymous stream 
        409
            Bundle stream with the specified pathname already exists

        Available Since
        ---------------
        0.3
        """
        # Work around bug https://bugs.launchpad.net/lava-dashboard/+bug/771182
        # Older clients would send None as the name and this would trigger an
        # IntegrityError to be raised by BundleStream.objects.create() below
        # which in turn would be captured by the fault handler and reported as
        # an unrelated issue to the user. Let's work around that by using an
        # empty string instead.
        if name is None:
            name = ""
        try:
            user_name, group_name, slug, is_public, is_anonymous = BundleStream.parse_pathname(pathname)
        except ValueError as ex:
            raise xmlrpclib.Fault(errors.FORBIDDEN, str(ex))

        # Start with those to simplify the logic below
        user = None
        group = None
        if is_anonymous is False:
            if self.user is not None:
                assert is_anonymous is False
                assert self.user is not None
                if user_name is not None:
                    if user_name != self.user.username:
                        raise xmlrpclib.Fault(
                            errors.FORBIDDEN,
                            "Only user {user!r} could create this stream".format(user=user_name))
                    user = self.user  # map to real user object
                elif group_name is not None:
                    try:
                        group = self.user.groups.get(name=group_name)
                    except Group.DoesNotExist:
                        raise xmlrpclib.Fault(
                            errors.FORBIDDEN,
                            "Only a member of group {group!r} could create this stream".format(group=group_name))
            else:
                assert is_anonymous is False
                assert self.user is None
                raise xmlrpclib.Fault(
                    errors.FORBIDDEN, "Only anonymous streams can be constructed (you are not signed in)")
        else:
            assert is_anonymous is True
            assert user_name is None
            assert group_name is None
            # Hacky but will suffice for now
            user = User.objects.get_or_create(username="anonymous-owner")[0]
        try:
            bundle_stream = BundleStream.objects.create(
                user=user,
                group=group,
                slug=slug,
                is_public=is_public,
                is_anonymous=is_anonymous,
                name=name)
        except IntegrityError:
            raise xmlrpclib.Fault(
                errors.CONFLICT,
                "Stream with the specified pathname already exists")
        else:
            return bundle_stream.pathname

    def data_views(self):
        """
        Name
        ----
        `data_views` ()

        Description
        -----------
        List all data views

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array of XML-RPC structs with
        the following fields:

        `name`: string
            Data view name declared in the definition file
        `summary`: string
            One-line description string suitable for developers

        Exceptions raised
        -----------------
        None
        """
        return [{
            'name': data_view.name,
            'summary': data_view.summary,
            "documentation": data_view.documentation,
            "arguments": [{
                "name": arg.name,
                "type": arg.type,
                "help": arg.help,
                "default": arg.default
            } for arg in data_view.arguments]
        } for data_view in DataView.repository.all()]

    def data_view_info(self, name):
        """
        Name
        ----
        `data_view_info` (`name`)

        Description
        -----------
        Describe a specific data view. This function looks up data view by name and returns rich information. See below for details

        Arguments
        ---------
        `name`: string
            Name of the data view to lookup
             

        Return value
        ------------
        This function returns an XML-RPC struct with the following fields:

        `name`: string
            Data view name declared in the definition file
        `summary`: string
            One-line description string suitable for developers
        `documentation`: string
            Longer documentation that described the purpose and indented usage of this data view
        `sql`: string or null
            The SQL of query specific to the currently running database (the
            actual query that is executed by query-data-view. Since some data
            views use database specific SQL the query may not be available.
        `argments` an XML-RPC array of XML-RPC structs with the following fields:
            `name`: Argument name
            `type`: Argument type, one of "number", "string" or "boolean"
            `help`: Help string for this argument
            `default`: Default value of an argument (or null if not available)


        Exceptions raised
        -----------------
        404
            Name does not designate a data view
        """
        try:
            data_view = DataView.repository.get(name=name)
        except DataView.DoesNotExist:
            raise xmlrpclib.Fault(errors.NOT_FOUND, "Data view not found")
        else:
            query = data_view.get_backend_specific_query(self.data_view_connection)
            return {
                "name": data_view.name,
                "summary": data_view.summary,
                "documentation": data_view.documentation,
                "sql": query.sql_template if query is not None else None, 
                "arguments": [{
                    "name": arg.name,
                    "type": arg.type,
                    "help": arg.help,
                    "default": arg.default
                } for arg in data_view.arguments]
            }

    def query_data_view(self, name, arguments):
        """
        Name
        ----
        `query_data_view` (name, arguments)

        Description
        -----------
        List all data views

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC struct with the following fields:

        `rows`: XML-RPC array of XML-RPC arrays
            Each item corresponds to cell in a row
        `columns`: XML-RPC array of XML-RPC structs with the following fields:
            `name`: XML-RPC string - name of the column
            `type`: XML-RPC string - column type (future extension, currently unused)

        Exceptions raised
        -----------------
        TBD
        """
        try:
            data_view = DataView.repository.get(name=name)
        except DataView.DoesNotExist:
            raise xmlrpclib.Fault(errors.NOT_FOUND, "Data view not found")
        try:
            rows, columns = data_view(self.data_view_connection, **arguments)
        except (LookupError, TypeError, ValueError, DatabaseError) as exc:
            raise xmlrpclib.Fault(errors.INTERNAL_SERVER_ERROR, str(exc))
        else:
            rows = [[float(cell) if isinstance(cell, decimal.Decimal) else cell for cell in row] for row in rows]
            return {
                "rows": rows,
                "columns": [{
                    "name": item[0],
                    "type": item[1]
                } for item in columns]
            }


# Mapper used by the legacy URL
legacy_mapper = Mapper()
legacy_mapper.register_introspection_methods()
legacy_mapper.register(DashboardAPI, '')
