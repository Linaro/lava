# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import logging
import os

import yaml
from django.core.exceptions import PermissionDenied
from django.db import DataError
from django.utils.translation import ngettext_lazy

from lava_common.yaml import yaml_safe_load
from linaro_django_xmlrpc.models import AuthToken


def help_max_length(max_length):
    return ngettext_lazy(
        "Maximum length: {0} character", "Maximum length: {0} characters", max_length
    ).format(max_length)


class StreamEcho:
    def write(self, value):
        return value


def description_filename(job):
    filename = os.path.join(job.output_dir, "description.yaml")
    if not os.path.exists(filename):
        return None
    return filename


def description_data(job):
    logger = logging.getLogger("lava_results_app")
    filename = description_filename(job)
    if not filename:
        return {}

    data = None
    try:
        with open(filename) as f_in:
            data = yaml_safe_load(f_in)
    except yaml.YAMLError as exc:
        logger.warning("Unable to parse description for %s", job.id)
    except OSError as exc:
        logger.error("Unable to open description for %s", job.id)
        logger.exception(exc)
    # This should be a dictionary, None is not acceptable
    return data if data else {}


# FIXME: relocate these two functions into dbutils to avoid needing django settings here.
# other functions in utils can be run outside django. Remove import of AuthToken.
def anonymous_token(request, job):
    querydict = request.GET
    user = querydict.get("user", default=None)
    token = querydict.get("token", default=None)
    # safe to call with (None, None) - returns None
    auth_user = AuthToken.get_user_for_secret(username=user, secret=token)
    return auth_user


def check_request_auth(request, job):
    if not request.user.is_authenticated:
        if not job.can_view(request.user):
            # handle anonymous access
            auth_user = anonymous_token(request, job)
            if not auth_user or not job.can_view(auth_user):
                raise PermissionDenied()
    elif not job.can_view(request.user):
        raise PermissionDenied()


def get_testcases_with_limit(testsuite, limit=None, offset=None):
    logger = logging.getLogger("lava_results_app")
    if limit:
        try:
            if not offset:
                testcases = list(testsuite.testcase_set.all().order_by("id")[:limit])
            else:
                testcases = list(
                    testsuite.testcase_set.all().order_by("id")[offset:][:limit]
                )
        except ValueError as e:
            logger.warning("Offset and limit must be integers: %s", str(e))
            return []
        except DataError as e:
            logger.warning("Offset must be positive integer: %s", str(e))
            return []
    else:
        testcases = list(testsuite.testcase_set.all().order_by("id"))

    return testcases


def testcase_export_fields():
    """
    Keep this list in sync with the keys in export_testcase
    :return: list of fields used in export_testcase
    """
    return [
        "job",
        "suite",
        "result",
        "measurement",
        "unit",
        "duration",
        "timeout",
        "logged",
        "level",
        "metadata",
        "url",
        "name",
        "id",
        "log_start_line",
        "log_end_line",
    ]


def export_testcase(testcase):
    """
    Returns string versions of selected elements of a TestCase
    Unicode causes issues with CSV and can complicate YAML parsing
    with non-python parsers.
    :param testcase: list of TestCase objects
    :return: Dictionary containing relevant information formatted for export
    """
    metadata = {}
    with contextlib.suppress(ValueError):
        metadata = dict(testcase.action_metadata) if testcase.action_metadata else {}
    extra_source = []
    extra_data = metadata.get("extra")
    if isinstance(extra_data, str) and os.path.exists(extra_data):
        items = {}
        with open(metadata["extra"]) as extra_file:
            with contextlib.suppress(yaml.YAMLError):
                items = yaml_safe_load(extra_file)
        # hide the !!python OrderedDict prefix from the output.
        for key, value in items.items():
            extra_source.append({key: value})
        metadata["extra"] = extra_source
    return {
        "name": str(testcase.name),
        "job": str(testcase.suite.job_id),
        "suite": str(testcase.suite.name),
        "result": str(testcase.result_code),
        "measurement": str(testcase.measurement),
        "unit": str(testcase.units),
        "level": metadata.get("level", ""),
        "url": str(testcase.get_absolute_url()),
        "id": str(testcase.id),
        "logged": str(testcase.logged),
        "log_start_line": str(testcase.start_log_line)
        if testcase.start_log_line
        else "",
        "log_end_line": str(testcase.end_log_line) if testcase.end_log_line else "",
        "metadata": metadata,
    }
