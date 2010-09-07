"""
Helper functions for making fixtures that setup specific environment
"""

from contextlib import contextmanager

from django.contrib.auth.models import (User, Group)
from django.core.files.base import ContentFile

from launch_control.dashboard_app.models import (
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


def use_test_scenarios(*scenarios):
    """
    Helper decorator for test cases that use scenarios.
    Turns wrapped function into a parametrized test case.

    scenarios is a list of tuples(scenario_name, args)
    args must be a dictionary, it is passed as keyword
    arguments to the test case function.

    Any test failures will be annotated with scenario name.
    """
    def run_with_scenarios(func):
        def decorator(self):
            if not scenarios:
                effective_scenarios = self.scenarios
            else:
                effective_scenarios = scenarios
            with test_loop(effective_scenarios) as loop_items:
                for scenario_name, values in loop_items:
                    try:
                        func(self, **values)
                    except Exception, ex:
                        self.fail("Unexpectedly failed with scenario {0!r}: {1!r}".format(
                            scenario_name, ex))
        return decorator
    return run_with_scenarios


@contextmanager
def created_bundle_streams(spec):
    """
    Helper context manager that creates bundle streams according to
    specification

    spec is a list of dictionaries with the following keys:
        user: string indicating user name to create [optional]
        group: string indicating group name to create [optional]
        slug: slug-like name [optional]
        name: name of the stream to create [optional]

    yields: list of created bundle streams
    """
    users = set()
    groups = set()
    bundle_streams = []
    for stream_args in spec:
        initargs = {
                'user': None,
                'group': None,
                'slug': stream_args.get('slug', ''),
                'name': stream_args.get('name', '')}
        username = stream_args.get('user')
        if username:
            user = User.objects.get_or_create(username=username)[0]
            users.add(user)
            initargs['user'] = user
        groupname = stream_args.get('group')
        if groupname:
            group = Group.objects.get_or_create(name=groupname)[0]
            groups.add(group)
            initargs['group'] = group
        bundle_stream = BundleStream.objects.create(**initargs)
        bundle_stream.save()
        bundle_streams.append(bundle_stream)
    yield bundle_streams
    for bundle_stream in bundle_streams:
        bundle_stream.delete()
    for user in users:
        user.delete()
    for group in groups:
        group.delete()


@contextmanager
def created_bundles(spec):
    """
    Helper context manager that creates bundles according to specification

    spec is a list of dictionaries with the following keys:
        pathname: string either "/anonymous/" or "/anonymous/SLUG/"
        content: string, text of the bundle
        content_filename: string

    yields: list of created bundles
    """
    bundle_streams = {}
    bundles = []
    users = set()
    groups = set()
    # make all bundle streams required  
    for pathname, content_filename, content in spec:
        pathname_parts = pathname.split('/')
        if len(pathname_parts) < 3:
            raise ValueError("Pathname to short: %r" % pathname)
        if pathname_parts[0] != '':
            raise ValueError("Pathname must be absolute: %r" % pathname)
        if pathname_parts[1] == 'anonymous':
            user = None
            group = None
            slug = pathname_parts[2]
            correct_length = 2
        elif pathname_parts[1] == 'personal':
            if len(pathname_parts) < 4:
                raise ValueError("Pathname to short: %r" % pathname)
            user = User.objects.create(username=pathname_parts[2])
            user.save()
            users.add(user)
            group = None
            slug = pathname_parts[3]
            correct_length = 3
        elif pathname_parts[1] == 'team':
            if len(pathname_parts) < 4:
                raise ValueError("Pathname to short: %r" % pathname)
            user = None
            group = Group.objects.create(name=pathname_parts[2])
            group.save()
            groups.add(group)
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
    # Note: We explicitly remove bundles because our @uses_scenarios
    # wrapper does not cope with pristine database configuration Also
    # because of FileFilelds() we need to call delete to get rid of test
    # files in the file system 
    for bundle in bundles:
        bundle.delete()
    for bundle_stream in bundle_streams.itervalues():
        bundle_stream.delete()
    for user in users:
        user.delete()
    for group in groups:
        group.delete()
