from django.utils.version import get_version


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
