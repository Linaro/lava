# -*- coding: utf-8 -*-
# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import os
import yaml
import logging

from django.db import DataError
from django.core.exceptions import PermissionDenied
from django.utils.translation import ungettext_lazy

from lava_common.compat import yaml_load
from linaro_django_xmlrpc.models import AuthToken


def help_max_length(max_length):
    return ungettext_lazy(  # pylint: disable=no-member
        u"Maximum length: {0} character", u"Maximum length: {0} characters", max_length
    ).format(max_length)


class StreamEcho:  # pylint: disable=too-few-public-methods
    def write(self, value):  # pylint: disable=no-self-use,
        return value


def description_filename(job):
    filename = os.path.join(job.output_dir, "description.yaml")
    if not os.path.exists(filename):
        return None
    return filename


try:
    from yaml import FullLoader as Loader
except ImportError:
    from yaml import Loader


class V2Loader(Loader):
    def remove_pipeline_module(self, suffix, node):
        if "lava_dispatcher.pipeline" in suffix:
            suffix = suffix.replace("lava_dispatcher.pipeline", "lava_dispatcher")

        # Fix deployment_data
        if "deployment_data_dict" in suffix:
            return self.construct_mapping(node.value[0][1])

        return self.construct_python_object(suffix, node)

    def remove_pipeline_module_name(self, suffix, node):
        # Fix old dumps when "pipeline" was a module
        if "lava_dispatcher.pipeline" in suffix:
            suffix = suffix.replace("lava_dispatcher.pipeline", "lava_dispatcher")
        # Fix dumps when dispatcher exceptions where not in lava_common.
        exceptions = [
            "ConfigurationError",
            "InfrastructureError",
            "JobCanceled",
            "JobError",
            "LAVABug",
            "MultinodeProtocolTimeoutError",
            "TestError",
        ]
        for exc in exceptions:
            if "lava_dispatcher.action.%s" % exc in suffix:
                suffix = suffix.replace(
                    "lava_dispatcher.action.%s" % exc, "lava_common.exceptions.%s" % exc
                )
        return self.construct_python_name(suffix, node)

    def remove_pipeline_module_new(self, suffix, node):
        if "lava_dispatcher.pipeline" in suffix:
            suffix = suffix.replace("lava_dispatcher.pipeline", "lava_dispatcher")
        return self.construct_python_object_new(suffix, node)


V2Loader.add_multi_constructor(
    u"tag:yaml.org,2002:python/name:", V2Loader.remove_pipeline_module_name
)
V2Loader.add_multi_constructor(
    u"tag:yaml.org,2002:python/object:", V2Loader.remove_pipeline_module
)
V2Loader.add_multi_constructor(
    u"tag:yaml.org,2002:python/object/new:", V2Loader.remove_pipeline_module_new
)


def description_data(job):
    logger = logging.getLogger("lava_results_app")
    filename = description_filename(job)
    if not filename:
        return {}

    data = None
    try:
        data = yaml.load(open(filename, "r"), Loader=V2Loader)
    except yaml.YAMLError as exc:
        logger.error("Unable to parse description for %s", job.id)
        logger.exception(exc)
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


def export_testcase(testcase, with_buglinks=False):
    """
    Returns string versions of selected elements of a TestCase
    Unicode causes issues with CSV and can complicate YAML parsing
    with non-python parsers.
    :param testcase: list of TestCase objects
    :return: Dictionary containing relevant information formatted for export
    """
    metadata = dict(testcase.action_metadata) if testcase.action_metadata else {}
    extra_source = []
    extra_data = metadata.get("extra")
    if isinstance(extra_data, str) and os.path.exists(extra_data):
        with open(metadata["extra"], "r") as extra_file:
            # TODO: this can fail!
            items = yaml_load(extra_file)
        # hide the !!python OrderedDict prefix from the output.
        for key, value in items.items():
            extra_source.append({key: value})
        metadata["extra"] = extra_source
    casedict = {
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
    if with_buglinks:
        casedict["buglinks"] = [
            str(url) for url in testcase.buglinks.values_list("url", flat=True)
        ]

    return casedict
