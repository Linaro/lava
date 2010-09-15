"""
Helper functions for making fixtures that setup specific environment
"""

from contextlib import contextmanager

from django.contrib.auth.models import (User, Group)
from django.core.files.base import ContentFile

from dashboard_app.models import (
        Bundle,
        BundleStream,
        )


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


def make_bundle_stream(stream_args):
    """
    Helper that creates a bundle stream according to specification

    stream_args is a dictionary with the following keys:
        user: string indicating user name to create [optional]
        group: string indicating group name to create [optional]
        slug: slug-like name [optional] (defaults to empty string)
        name: name of the stream to create [optional]
    """
    initargs = {
            'user': None,
            'group': None,
            'slug': stream_args.get('slug', ''),
            'name': stream_args.get('name', '')}
    username = stream_args.get('user')
    if username:
        user = User.objects.get_or_create(username=username)[0]
        initargs['user'] = user
    groupname = stream_args.get('group')
    if groupname:
        group = Group.objects.get_or_create(name=groupname)[0]
        initargs['group'] = group
    bundle_stream = BundleStream.objects.create(**initargs)
    bundle_stream.save()
    return bundle_stream


@contextmanager
def created_bundle_streams(spec):
    """
    Helper context manager that creates bundle streams according to
    specification.

    `spec`: list of dictionaries
        List of values to make_bundle_stream()

    yields: list of BundleStream
        List of created bundle stream objects
    """
    bundle_streams = []
    for stream_args in spec:
        bundle_streams.append(make_bundle_stream(stream_args))
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
    bundle_streams = {}
    bundles = []
    # make all bundle streams required
    for pathname, content_filename, content in spec:
        pathname_parts = pathname.split('/')
        if len(pathname_parts) < 3:
            raise ValueError("Pathname too short: %r" % pathname)
        if pathname_parts[0] != '':
            raise ValueError("Pathname must be absolute: %r" % pathname)
        if pathname_parts[1] == 'anonymous':
            user = None
            group = None
            slug = pathname_parts[2]
            correct_length = 2
        elif pathname_parts[1] == 'personal':
            if len(pathname_parts) < 4:
                raise ValueError("Pathname too short: %r" % pathname)
            user = User.objects.create(username=pathname_parts[2])
            user.save()
            group = None
            slug = pathname_parts[3]
            correct_length = 3
        elif pathname_parts[1] == 'team':
            if len(pathname_parts) < 4:
                raise ValueError("Pathname too short: %r" % pathname)
            user = None
            group = Group.objects.create(name=pathname_parts[2])
            group.save()
            slug = pathname_parts[3]
            correct_length = 3
        else:
            raise ValueError("Invalid pathname primary designator: %r" % pathname)
        if slug != '':
            correct_length += 1
        if pathname_parts[correct_length:] != ['']:
            raise ValueError("Junk after pathname: %r" % pathname)
        if pathname not in bundle_streams:
            bundle_stream = BundleStream.objects.create(
                    user=user, group=group, slug=slug)
            bundle_stream.save()
            bundle_streams[pathname] = bundle_stream
    # make all bundles
    for pathname, content_filename, content in spec:
        bundle = Bundle.objects.create(
                bundle_stream=bundle_streams[pathname],
                content_filename=content_filename)
        bundle.content.save(content_filename, ContentFile(content))
        bundle.save()
        bundles.append(bundle)
    # give bundles back
    yield bundles
    # clean up
    # Note: We explicitly remove bundles because of FileField artefacts
    # that get left behind.
    for bundle in bundles:
        bundle.delete()
