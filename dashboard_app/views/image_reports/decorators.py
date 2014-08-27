from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.decorators import available_attrs
from django.utils.functional import wraps

from dashboard_app.models import ImageReport


def ownership_required(view_func):
    @wraps(view_func, assigned=available_attrs(view_func))
    def wrapper(request, *args, **kwargs):
        report_name = kwargs.get('name', None)
        image_report = get_object_or_404(ImageReport, name=report_name)
        if request.user.is_superuser or image_report.user == request.user:
                return view_func(request, *args, **kwargs)
        else:
            raise PermissionDenied
    return wrapper


def public_filters_or_login_required(view_func):
    @wraps(view_func, assigned=available_attrs(view_func))
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated():
            report_name = kwargs.get('name', None)
            image_report = get_object_or_404(ImageReport, name=report_name)
            for image_chart in image_report.imagereportchart_set.all():
                for chart_filter in image_chart.imagechartfilter_set.all():
                    if not chart_filter.filter.public:
                        raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper
