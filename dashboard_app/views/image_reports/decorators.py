from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.decorators import available_attrs
from django.utils.functional import wraps

from dashboard_app.models import ImageReport


def ownership_required(view_func):
    @wraps(view_func, assigned=available_attrs(view_func))
    def wrapper(request, *args, **kwargs):
        report_name = kwargs.get('name', None)
        image_report = ImageReport.objects.get(name=report_name)
        if image_report.user == request.user:
            return view_func(request, *args, **kwargs)
        else:
            raise PermissionDenied
    return wrapper

