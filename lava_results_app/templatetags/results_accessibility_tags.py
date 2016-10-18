from django import template


register = template.Library()


@register.assignment_tag
def is_accessible_by(record, user):
    try:
        return record.is_accessible_by(user)
    except (TypeError, AttributeError, IndexError):
        return False
