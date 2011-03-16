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
Helper functions for making fixtures that setup specific environment
"""

from contextlib import contextmanager

from django.contrib.auth.models import (User, Group)

from dashboard_app.models import (Bundle, BundleStream)


class test_loop(object):
    """
    Support class that tells you something about a test crashing when
    the actual test values depend on a loop value
    """

    def __init__(self, source):
        self._iter = iter(source)
        self._last = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            import logging
            logging.exception("Exception in test_loop on iteration: %r", self._last)

    def __iter__(self):
        return self

    def next(self):
        self._last = next(self._iter)
        return self._last


def create_bundle_stream(pathname):
    """
    Create, or get an existing bundle stream designated by the provided
    pathname. The pathname is parsed and decomposed to determine the
    user/group and slug. Users and groups are created if necessary.
    """
    try:
        return BundleStream.objects.get(pathname=pathname)
    except BundleStream.DoesNotExist:
        user_username, group_name, slug, is_public, is_anonymous = BundleStream.parse_pathname(pathname)
        if user_username is None and group_name is None:
            # Here we trick a little - since the introduction of the
            # django-restricted-resource each object has a principal
            # owner - either a user or a group. This information can be
            # conveyed from the pathname _except_ for anonymous streams
            # that are a remnant of the past. For those streams we just
            # create a dummy user.
            user_username = "anonymous-stream-owner"
        if user_username is not None:
            user = User.objects.get_or_create(username=user_username)[0]
        else:
            user = None
        if group_name is not None:
            group = Group.objects.get_or_create(name=group_name)[0]
        else:
            group = None
        bundle_stream = BundleStream.objects.create(
            user=user, group=group, slug=slug,
            is_public=is_public, is_anonymous=is_anonymous)
        bundle_stream.save()
        return bundle_stream


def create_bundle(pathname, content, content_filename):
    """"
    Create bundle with the specified content and content_filename and
    place it in a bundle stream designated by the specified pathname.
    Bundle stream is created if required.
    """
    return Bundle.objects.create_with_content(
        bundle_stream=create_bundle_stream(pathname),
        uploaded_by=None,
        content_filename=content_filename,
        content=content)


@contextmanager
def created_bundle_streams(pathnames):
    """
    Helper context manager that creates bundle streams according to
    specification.

    `pathnames`: list of pathnames to create
        List of values to create_bundle_stream()

    yields: list of BundleStream
        List of created bundle stream objects
    """
    bundle_streams = []
    for pathname in pathnames:
        bundle_streams.append(create_bundle_stream(pathname))
    yield bundle_streams


@contextmanager
def created_bundles(spec):
    """
    Helper context manager that creates bundles according to specification

    spec is a list of 3-element tuples:
        pathname: string, bundle stream pathname (all variants supported)
        content: string, text of the bundle
        content_filename: string

    yields: list of created bundles
    """
    bundles = []
    for pathname, content_filename, content in spec:
        bundles.append(
            create_bundle(pathname, content, content_filename))
    yield bundles
    for bundle in bundles:
        bundle.delete_files()
