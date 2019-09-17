from django.utils.version import get_version
from django.core.management.base import CommandParser


DJANGO_VERSION = get_version()


# Handles compatibility for django_restframework_filters
try:
    from rest_framework_filters.backends import RestFrameworkFilterBackend  # noqa
except ImportError:
    from rest_framework_filters.backends import (
        DjangoFilterBackend as RestFrameworkFilterBackend,
    )  # noqa

FilterBackend = RestFrameworkFilterBackend


def add_permissions(default_in_django2, local):
    if DJANGO_VERSION >= "2":
        return local
    else:
        return default_in_django2 + local


def get_sub_parser_class(cmd):
    class SubParser(CommandParser):
        """
        Sub-parsers constructor that mimic Django constructor.
        See http://stackoverflow.com/a/37414551
        """

        def __init__(self, **kwargs):
            if DJANGO_VERSION >= "2":
                super().__init__(**kwargs)
            else:
                super().__init__(cmd, **kwargs)

    return SubParser
