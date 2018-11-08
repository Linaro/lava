# -*- coding: utf-8 -*-
# Copyright (C) 2017-2018 Linaro Limited
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

import re
from django import template
from django.conf import settings
from collections import OrderedDict
from django.utils.safestring import mark_safe
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
action_id_regexp = re.compile(r'^start: ([\d.]+) [\w_-]+ ')


@register.assignment_tag
def get_action_id(string):
    try:
        return action_id_regexp.match(string).group(1).replace('.', '-')
    except (TypeError, AttributeError, IndexError):
        return ''


@register.filter
def replace_dots(string):
    return string.replace('.', '-')


@register.assignment_tag()
def assign_setting(value):
    """Returns the value of the setting"""
    if hasattr(settings, value):
        return getattr(settings, value)


def _get_pipeline_data(pipeline, levels):
    """
    Recursive check on the pipeline description dictionary
    """
    for action in pipeline:
        levels[action['level']] = {
            'name': action['name'],
            'description': action['description'],
            'summary': action['summary'],
            'timeout': action['timeout'],
        }
        if 'url' in action:
            levels[action['level']].update({'url': action['url']})
        if 'pipeline' in action:
            _get_pipeline_data(action['pipeline'], levels)


@register.assignment_tag()
def get_pipeline_sections(pipeline):
    """
    Just a top level view of the pipeline sections
    """
    sections = []
    for action in pipeline:
        if 'section' in action:
            sections.append({action['section']: action['level']})
    return sections


@register.assignment_tag()
def get_pipeline_levels(pipeline):
    """
    Retrieve the full set of action levels in this pipeline.
    """
    levels = OrderedDict()
    _get_pipeline_data(pipeline, levels)
    return levels


@register.filter()
def deploy_methods(device_type, methods):
    data = load_devicetype_template(device_type)
    if not data or 'actions' not in data or methods not in data['actions']:
        return []
    methods = data['actions'][methods]['methods']
    if isinstance(methods, dict):
        return methods.keys()
    return [methods]


@register.assignment_tag()
def device_type_timeouts(device_type):
    data = load_devicetype_template(device_type)
    if not data or 'timeouts' not in data:
        return None
    return data['timeouts']


@register.filter()
def result_url(result_dict, job_id):
    if not isinstance(result_dict, dict):
        return None
    if 'test_definition' in result_dict:
        testdef = result_dict['test_definition']
        testcase = None
        for key, _ in result_dict.items():
            if key == 'test_definition':
                continue
            testcase = key
            break
        # 8125/singlenode-intermediate/tar-tgz
        return mark_safe('/results/%s/%s/%s' % (
            job_id, testdef, testcase
        ))
    elif len(result_dict.keys()) == 1:
        # action based result
        testdef = 'lava'
        if isinstance(result_dict.values()[0], OrderedDict):
            testcase = result_dict.keys()[0]
            return mark_safe('/results/%s/%s/%s' % (
                job_id, testdef, testcase
            ))
    else:
        return None


@register.filter()
def markup_metadata(key, value):
    if 'target.device_type' in key:
        return mark_safe("<a href='/scheduler/device_type/%s'>%s</a>" % (value, value))
    elif 'target.hostname' in key:
        return mark_safe("<a href='/scheduler/device/%s'>%s</a>" % (value, value))
    elif 'definition.repository' in key and value.startswith('http'):
        return mark_safe("<a href='%s'>%s</a>" % (value, value))
    else:
        return value


@register.assignment_tag
def can_view(record, user):
    try:
        return record.can_view(user)
    except Exception:
        return False


@register.filter()
def split_definition(data):
    # preserve comments
    # rstrip() gets rid of the empty new line.
    return data.rstrip().split('\n') if data else []


@register.filter()
def level_replace(level):
    return level.replace('.', '-')


@register.filter()
def sort_items(items):
    return sorted(items)


@register.filter()
def replace_python_unicode(data):
    return data.replace('!!python/unicode ', '')


@register.filter
def get_api_by_section(methods, api):
    ret = ''
    sections = sorted(set([block['section'] for block in methods[api]]))
    for section in sections:
        if section:
            ret += mark_safe("<h3>%s</h3>" % section)
        for method in methods[api]:
            if method['section'] == section:
                ret += mark_safe('[&nbsp;<a href="#%s">%s</a>&nbsp;]' % (method['name'], method['name']))
    return mark_safe(ret)
