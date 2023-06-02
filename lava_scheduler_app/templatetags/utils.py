# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import re
from collections import OrderedDict

from django import template
from django.conf import settings
from django.utils.html import format_html

from lava_scheduler_app.dbutils import load_devicetype_template

register = template.Library()


@register.filter
def udecode(obj):
    # Sometime we do have unicode string: they have been already decoded, so we
    # should not do anything.
    # The only way to test for unicode string in both python2 and 3, is to test
    # for the bytes type.
    if not isinstance(obj, bytes):
        return obj
    try:
        return obj.decode("utf-8", errors="replace")
    except AttributeError:
        return obj


# Compile it only once
action_id_regexp = re.compile(r"^start: ([\d.]+) [\w_-]+ ")


@register.simple_tag
def get_action_id(string):
    try:
        return action_id_regexp.match(string).group(1).replace(".", "-")
    except (TypeError, AttributeError, IndexError):
        return ""


@register.filter
def replace_dots(string):
    return string.replace(".", "-")


@register.simple_tag
def assign_setting(value):
    """Returns the value of the setting"""
    if hasattr(settings, value):
        return getattr(settings, value)


@register.filter()
def deploy_methods(device_type, methods):
    data = load_devicetype_template(device_type)
    if not data or "actions" not in data or methods not in data["actions"]:
        return []
    methods = data["actions"][methods]["methods"]
    if isinstance(methods, dict):
        return methods.keys()
    return [methods]


@register.simple_tag
def device_type_timeouts(device_type):
    data = load_devicetype_template(device_type)
    if not data or "timeouts" not in data:
        return None
    return data["timeouts"]


@register.filter()
def result_url(result_dict, job_id):
    if not isinstance(result_dict, dict):
        return None
    if "test_definition" in result_dict:
        testdef = result_dict["test_definition"]
        testcase = None
        for key, _ in result_dict.items():
            if key == "test_definition":
                continue
            testcase = key
            break
        # 8125/singlenode-intermediate/tar-tgz
        return format_html("/results/{}/{}/{}", job_id, testdef, testcase)
    elif len(result_dict.keys()) == 1:
        # action based result
        testdef = "lava"
        if isinstance(result_dict.values()[0], OrderedDict):
            testcase = result_dict.keys()[0]
            return format_html("/results/{}/{}/{}", job_id, testdef, testcase)
    else:
        return None


@register.filter()
def markup_metadata(key, value):
    if "target.device_type" in key:
        return format_html("<a href='/scheduler/device_type/{}'>{}</a>", value, value)
    elif "target.hostname" in key:
        return format_html("<a href='/scheduler/device/{}'>{}</a>", value, value)
    elif "definition.repository" in key and value.startswith("http"):
        return format_html("<a href='{}'>{}</a>", value, value)
    else:
        return value


@register.filter()
def split_definition(data):
    # preserve comments
    # rstrip() gets rid of the empty new line.
    return data.rstrip().split("\n") if data else []


@register.filter()
def level_replace(level):
    return level.replace(".", "-")


@register.filter()
def sort_items(items):
    return sorted(items)


@register.filter()
def replace_python_unicode(data):
    return data.replace("!!python/unicode ", "")
