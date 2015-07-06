import os
import yaml
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
from lava_scheduler_app.models import TestJob
from lava_scheduler_app.models import (
    DeviceDictionary,
    DeviceDictionaryTable,
    JobPipeline,
    PipelineStore,
)


register = template.Library()


@register.filter
def get_priority_select(current):
    select = ""
    val = TestJob.PRIORITY_CHOICES
    for priority, label in val:
        check = " checked" if priority == current else ""
        default = " [default]" if current != 50 and priority == 50 else ""
        select += '<label class="checkbox-inline">'
        select += '<input type="radio" name="priority" style="..." id="%s" value="%d"%s>%s%s</input><br/>' %\
                  (label.lower(), priority, check, label, default)
        select += '</label>'
    return mark_safe(select)


@register.filter
def get_type(value):
    """
    Detects iterable types from not iterable types
    enough for the templates to work out if it is a value or a key.
    """
    if type(value) == str:
        return 'str'
    if type(value) == unicode:
        return 'str'
    if type(value) == bool:
        return 'str'
    if type(value) == int:
        return 'str'
    if type(value) == dict:
        return 'dict'
    if type(value) == list:
        return 'list'
    return type(value)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_device_dictionary(data):
    key = os.path.basename(os.path.dirname(data))
    device_dict_obj = DeviceDictionaryTable.objects.get(id=key)
    device_dict = device_dict_obj.lookup_device_dictionary()
    return device_dict.to_dict()


@register.filter
def get_pipeline_store(data):
    key = os.path.basename(os.path.dirname(data))
    device_dict_obj = PipelineStore.objects.get(id=key)
    device_dict = device_dict_obj.lookup_job_pipeline()
    return device_dict.to_dict()


@register.filter
def get_device_parameters(data, key):
    if type(data) == str:
        return data
    if type(data) == dict:
        if type(key) == str and key in data:
                return data.get(key)
        return key.keys()
    return (type(data), type(key), data)


@register.filter
def get_yaml_parameters(parameters):
    # FIXME: it should be possible to dump this dict as YAML.
    try:
        ret = yaml.safe_dump(parameters, default_flow_style=False, canonical=False, default_style=None)
    except:
        return parameters
    return ret


@register.filter
def get_settings(value):
    if hasattr(settings, value):
        return getattr(settings, value)
