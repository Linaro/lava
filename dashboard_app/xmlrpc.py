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

import datetime
import decimal
import logging
import re
import urllib2
import xmlrpclib
import hashlib
import json
import os
import subprocess
from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django.db import IntegrityError, DatabaseError
from linaro_django_xmlrpc.models import (
    ExposedAPI,
    Mapper,
    xml_rpc_signature,
)

from dashboard_app.filters import evaluate_filter
from dashboard_app.models import (
    Bundle,
    BundleStream,
    Test,
    TestRunFilter,
    TestDefinition,
)
from lava_scheduler_app.models import (
    TestJob,
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

        Description
        -----------
        Return lava server version. The version is a string, which is the
        Debian package version of lava-server pacakage.

        Return value
        -------------
        Lava server version string
        """
        cmd = ['dpkg-query', '-W', '-f', '${version}', 'lava-server']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.PIPE)
        out, err = proc.communicate()

        if not err:
            return out
        else:
            return 'unknown'

    def _put(self, content, content_filename, pathname):
        try:
            self.logger.debug("Getting bundle stream")
            if self.user and self.user.is_superuser:
                bundle_stream = BundleStream.objects.get(pathname=pathname)
            else:
                bundle_stream = BundleStream.objects.accessible_by_principal(self.user).get(pathname=pathname)
        except BundleStream.DoesNotExist:
            self.logger.debug("Bundle stream does not exist, aborting")
            raise xmlrpclib.Fault(errors.NOT_FOUND,
                                  "Bundle stream not found")
        if not bundle_stream.can_upload(self.user):
            raise xmlrpclib.Fault(
                errors.FORBIDDEN, "You cannot upload to this stream")
        try:
            self.logger.debug("Creating bundle object")
            bundle = Bundle.objects.create_with_content(bundle_stream, self.user, content_filename, content)
        except (IntegrityError, ValueError) as exc:
            self.logger.debug("Raising xmlrpclib.Fault(errors.CONFLICT)")
            raise xmlrpclib.Fault(errors.CONFLICT, str(exc))
        except:
            self.logger.exception("big oops")
            raise
        else:
            self.logger.debug("Deserializing bundle")
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
        self.logger.debug("Returning bundle SHA1")
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
        content_filename = urllib2.unquote(content_filename).decode('utf-8')
        bundle = self._put(content, content_filename, pathname)
        self.logger.debug("Returning permalink to bundle")
        return self._context.request.build_absolute_uri(
            reverse('dashboard_app.views.redirect_to_bundle',
                    kwargs={'content_sha1': bundle.content_sha1}))

    def put_pending(self, content, pathname, group_name):
        """
        Name
        ----
        `put_pending` (`content`, `pathname`, `group_name`)

        Description
        -----------
        MultiNode internal call.

        Stores the bundle until the coordinator allows the complete
        bundle list to be aggregated from the list and submitted by put_group

        Arguments
        ---------
        `content`: string
            Full text of the bundle. This *MUST* be a valid JSON
            document and it *SHOULD* match the "Dashboard Bundle Format
            1.0" schema. The SHA1 of the content *MUST* be unique or a
            ``Fault(409, "...")`` is raised. This is used to protect
            from simple duplicate submissions.
        `pathname`: string
            Pathname of the bundle stream where a new bundle should
            be created and stored. This argument *MUST* designate a
            pre-existing bundle stream or a ``Fault(404, "...")`` exception
            is raised. In addition the user *MUST* have access
            permission to upload bundles there or a ``Fault(403, "...")``
            exception is raised. See below for access rules.
        `group_name`: string
            Unique ID of the MultiNode group. Other pending bundles will
            be aggregated into a single result bundle for this group.

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
        try:
            self.logger.debug("Getting bundle stream")
            if self.user.is_superuser:
                bundle_stream = BundleStream.objects.get(pathname=pathname)
            else:
                bundle_stream = BundleStream.objects.accessible_by_principal(self.user).get(pathname=pathname)
        except BundleStream.DoesNotExist:
            self.logger.debug("Bundle stream does not exist, aborting")
            raise xmlrpclib.Fault(errors.NOT_FOUND,
                                  "Bundle stream not found")
        if not bundle_stream.can_upload(self.user):
            raise xmlrpclib.Fault(
                errors.FORBIDDEN, "You cannot upload to this stream")
        try:
            # add this to a list which put_group can use.
            sha1 = hashlib.sha1()
            sha1.update(content)
            hexdigest = sha1.hexdigest()
            groupfile = "/tmp/%s" % group_name
            with open(groupfile, "a+") as grp_file:
                grp_file.write("%s\n" % content)
            return hexdigest
        except Exception as e:
            self.logger.debug("Dashboard pending submission caused an exception: %s", e)

    def put_group(self, content, content_filename, pathname, group_name):
        """
        Name
        ----
        `put_group` (`content`, `content_filename`, `pathname`, `group_name`)

        Description
        -----------
        MultiNode internal call.

        Adds the final bundle to the list, aggregates the list
        into a single group bundle and submits the group bundle.

        Arguments
        ---------
        `content`: string
            Full text of the bundle. This *MUST* be a valid JSON
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
        `group_name`: string
            Unique ID of the MultiNode group. Other pending bundles will
            be aggregated into a single result bundle for this group. At
            least one other bundle must have already been submitted as
            pending for the specified MultiNode group. LAVA Coordinator
            causes the parent job to wait until all nodes have been marked
            as having pending bundles, even if some bundles are empty.

        Return value
        ------------
        If all goes well this function returns the full URL of the bundle.

        Exceptions raised
        -----------------
        ValueError:
            One or more bundles could not be converted to JSON prior
            to aggregation.
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
        grp_file = "/tmp/%s" % group_name
        bundle_set = {}
        bundle_set[group_name] = []
        if os.path.isfile(grp_file):
            with open(grp_file, "r") as grp_data:
                grp_list = grp_data.readlines()
            for testrun in grp_list:
                bundle_set[group_name].append(json.loads(testrun))
        # Note: now that we have the data from the group, the group data file could be re-used
        # as an error log which is simpler than debugging through XMLRPC.
        else:
            raise ValueError("Aggregation failure for %s - check coordinator rpc_delay?" % group_name)
        group_tests = []
        try:
            json_data = json.loads(content)
        except ValueError:
            self.logger.debug("Invalid JSON content within the sub_id zero bundle")
            json_data = None
        try:
            bundle_set[group_name].append(json_data)
        except Exception as e:
            self.logger.debug("appending JSON caused exception %s", e)
        try:
            for bundle_list in bundle_set[group_name]:
                for test_run in bundle_list['test_runs']:
                    group_tests.append(test_run)
        except Exception as e:
            self.logger.debug("aggregating bundles caused exception %s", e)
        group_content = json.dumps({"test_runs": group_tests, "format": json_data['format']})
        bundle = self._put(group_content, content_filename, pathname)
        self.logger.debug("Returning permalink to aggregated bundle for %s", group_name)
        permalink = self._context.request.build_absolute_uri(
            reverse('dashboard_app.views.redirect_to_bundle',
                    kwargs={'content_sha1': bundle.content_sha1}))
        # only delete the group file when things go well.
        if os.path.isfile(grp_file):
            os.remove(grp_file)
        return permalink

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
        - 404 Bundle not found
        - 403 Permission denied

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
                raise xmlrpclib.Fault(
                    403, "Permission denied.  User does not have permissions "
                    "to access this bundle.")
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
        if self.user and self.user.is_superuser:
            bundle_streams = BundleStream.objects.all()
        else:
            bundle_streams = BundleStream.objects.accessible_by_principal(
                self.user)
        return [
            {
                'pathname': bundle_stream.pathname,
                'name': bundle_stream.name,
                'user': bundle_stream.user.username if bundle_stream.user else "",
                'group': bundle_stream.group.name if bundle_stream.group else "",
                'bundle_count': bundle_stream.bundles.count(),
            }
            for bundle_stream in bundle_streams
        ]

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
            The size of the content
        `is_deserialized`: bool
            True if the bundle was de-serialized successfully, false otherwise
        `associated_job`: int
            The job with which this bundle is associated


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
        bundles = []
        try:
            if self.user and self.user.is_superuser:
                bundle_stream = BundleStream.objects.get(pathname=pathname)
            else:
                bundle_stream = BundleStream.objects.accessible_by_principal(self.user).get(pathname=pathname)
            for bundle in bundle_stream.bundles.all().order_by("uploaded_on"):
                job_id = 'NA'
                try:
                    job = TestJob.objects.get(_results_bundle=bundle)
                    job_id = job.id
                except TestJob.DoesNotExist:
                    job_id = 'NA'
                bundles.append({
                    'uploaded_by': bundle.uploaded_by.username if bundle.uploaded_by else "",
                    'uploaded_on': bundle.uploaded_on,
                    'content_filename': bundle.content_filename,
                    'content_sha1': bundle.content_sha1,
                    'content_size': bundle.content.size,
                    'is_deserialized': bundle.is_deserialized,
                    'associated_job': job_id
                })
        except BundleStream.DoesNotExist:
            raise xmlrpclib.Fault(errors.NOT_FOUND, "Bundle stream not found")
        return bundles

    @xml_rpc_signature('str')
    def get_test_names(self, device_type=None):
        """
        Name
        ----
        `get_test_names` ([`device_type`]])

        Description
        -----------
        Get the name of all the tests that have run on a particular device type.

        Arguments
        ---------
        `device_type`: string
            The type of device the retrieved test names should apply to.

        Return value
        ------------
        This function returns an XML-RPC array of test names.
        """
        test_names = []
        if device_type:
            for test in Test.objects.filter(
                    test_runs__attributes__name='target.device_type',
                    test_runs__attributes__value=device_type).distinct():
                test_names.append(test.test_id)
        else:
            for test in Test.objects.all():
                test_names.append(test.test_id)
        return test_names

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
                    if not self.user.is_superuser:
                        if user_name != self.user.username:
                            raise xmlrpclib.Fault(
                                errors.FORBIDDEN,
                                "Only user {user!r} could create this stream".format(user=user_name))
                    user = self.user  # map to real user object
                elif group_name is not None:
                    try:
                        if self.user.is_superuser:
                            group = Group.objects.get(name=group_name)
                        else:
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
            if self.user is not None:
                user = self.user
            else:
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

    def _get_filter_data(self, filter_name):
        match = re.match("~([-_A-Za-z0-9]+)/([-_A-Za-z0-9]+)", filter_name)
        if not match:
            raise xmlrpclib.Fault(errors.BAD_REQUEST, "filter_name must be of form ~owner/filter-name")
        owner_name, filter_name = match.groups()
        try:
            owner = User.objects.get(username=owner_name)
        except User.NotFound:
            raise xmlrpclib.Fault(errors.NOT_FOUND, "user %s not found" % owner_name)
        try:
            filter = TestRunFilter.objects.get(owner=owner, name=filter_name)
        except TestRunFilter.NotFound:
            raise xmlrpclib.Fault(errors.NOT_FOUND, "filter %s not found" % filter_name)
        if not filter.public and self.user != owner:
            if self.user:
                raise xmlrpclib.Fault(
                    errors.FORBIDDEN, "forbidden")
            else:
                raise xmlrpclib.Fault(
                    errors.AUTH_REQUIRED, "authentication required")
        return filter.as_data()

    def get_filter_results(self, filter_name, count=10, offset=0):
        """
        Name
        ----
         ::

          get_filter_results(filter_name, count=10, offset=0)

        Description
        -----------

        Return information about the test runs and results that a given filter
        matches.

        Arguments
        ---------

        ``filter_name``:
           The name of a filter in the format ~owner/name.
        ``count``:
           The maximum number of matches to return.
        ``offset``:
           Skip over this many results.

        Return value
        ------------

        A list of "filter matches".  A filter match describes the results of
        matching a filter against one or more test runs::

          {
            'tag': either a stringified date (bundle__uploaded_on) or a build number
            'test_runs': [{
                'test_id': test_id
                'link': link-to-test-run,
                'passes': int, 'fails': int, 'skips': int, 'total': int,
                # only present if filter specifies cases for this test:
                'specific_results': [{
                    'test_case_id': test_case_id,
                    'link': link-to-test-result,
                    'result': pass/fail/skip/unknown,
                    'measurement': string-containing-decimal-or-None,
                    'units': units,
                    }],
                }]
            # Only present if filter does not specify tests:
            'pass_count': int,
            'fail_count': int,
          }

        """
        filter_data = self._get_filter_data(filter_name)
        matches = evaluate_filter(self.user, filter_data, descending=False)
        matches = matches[offset:offset + count]
        return [match.serializable() for match in matches]

    def get_filter_results_since(self, filter_name, since=None):
        """
        Name
        ----
         ::

          get_filter_results_since(filter_name, since=None)

        Description
        -----------

        Return information about the test runs and results that a given filter
        matches that are more recent than a previous match -- in more detail,
        results where the ``tag`` is greater than the value passed in
        ``since``.

        The idea of this method is that it will be called from a cron job to
        update previously accessed results.  Something like this::

           previous_results = json.load(open('results.json'))
           results = previous_results + server.dashboard.get_filter_results_since(
              filter_name, previous_results[-1]['tag'])
           ... do things with results ...
           json.save(results, open('results.json', 'w'))

        If called without passing ``since`` (or with ``since`` set to
        ``None``), this method returns up to 100 matches from the filter.  In
        fact, the matches are always capped at 100 -- so set your cronjob to
        execute frequently enough that there are less than 100 matches
        generated between calls!

        Arguments
        ---------

        ``filter_name``:
           The name of a filter in the format ~owner/name.
        ``since``:
           The 'tag' of the most recent result that was retrieved from this
           filter.

        Return value
        ------------

        A list of "filter matches".  A filter match describes the results of
        matching a filter against one or more test runs::

          {
            'tag': either a stringified date (bundle__uploaded_on) or a build number
            'test_runs': [{
                'test_id': test_id
                'link': link-to-test-run,
                'passes': int, 'fails': int, 'skips': int, 'total': int,
                # only present if filter specifies cases for this test:
                'specific_results': [{
                    'test_case_id': test_case_id,
                    'link': link-to-test-result,
                    'result': pass/fail/skip/unknown,
                    'measurement': string-containing-decimal-or-None,
                    'units': units,
                    }],
                }]
            # Only present if filter does not specify tests:
            'pass_count': int,
            'fail_count': int,
          }

        """
        filter_data = self._get_filter_data(filter_name)
        matches = evaluate_filter(self.user, filter_data, descending=False)
        if since is not None:
            if filter_data.get('build_number_attribute') is not None:
                try:
                    since = datetime.datetime.strptime(since, "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    raise xmlrpclib.Fault(
                        errors.BAD_REQUEST, "cannot parse since argument as datetime")
            matches = matches.since(since)
        matches = matches[:100]
        return [match.serializable() for match in matches]

# Mapper used by the legacy URL
legacy_mapper = Mapper()
legacy_mapper.register_introspection_methods()
legacy_mapper.register(DashboardAPI, '')
