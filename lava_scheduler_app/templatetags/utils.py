from django import template
from django.utils.safestring import mark_safe
from lava_scheduler_app.models import TestJob

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
