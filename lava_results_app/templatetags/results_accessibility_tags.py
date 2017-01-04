from django import template


register = template.Library()


@register.assignment_tag
def is_accessible_by(record, user):
    try:
        return record.is_accessible_by(user)
    except (TypeError, AttributeError, IndexError):
        return False


@register.filter
def check_chart_access(record, user):
    access = True
    for query in record.queries.all():
        if not query.is_accessible_by(user):
            access = False
    return access
