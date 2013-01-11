# Copyright (C) 2010-2012 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.


from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response
from django.template import RequestContext

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from dashboard_app.filters import evaluate_filter
from dashboard_app.models import (
    BundleStream,
    PMQABundleStream,
    Test,
)
from dashboard_app.views import index
from dashboard_app.views.filters.tables import (
    FilterTable,
    )
from dashboard_app.views.filters.views import (
    compare_filter_matches,
    )


@BreadCrumb("PM QA view", parent=index)
@login_required
def pmqa_view(request):
    test = Test.objects.get(test_id='pwrmgmt')
    device_types_with_results = []
    prefix__device_type_result = {}

    from lava_scheduler_app.models import DeviceType
    device_types = list(DeviceType.objects.filter(display=True).values_list('name', flat=True))
    bundle_streams = [pmqabs.bundle_stream for pmqabs in PMQABundleStream.objects.all()]
    bundle_streams.sort(key=lambda bs:bs.pathname)

    for bs in bundle_streams:
        c = len(device_types_with_results)
        for device_type in device_types:
            if device_type.startswith('rtsm'):
                continue
            filter_data = {
                'bundle_streams': [bs],
                'attributes': [('target.device_type', device_type)],
                'tests': [{'test':test, 'test_cases':[]}],
                'build_number_attribute': 'build.id',
                }
            matches = list(evaluate_filter(request.user, filter_data)[:50])
            if matches:
                match = matches[0]
                m0 = match.serializable(include_links=False)
                del m0['tag']
                last_difference = None
                for m in matches[1:]:
                    m1 = m.serializable(include_links=False)
                    del m1['tag']
                    if m1 != m0:
                        last_difference = (
                            m.tag,
                            reverse(compare_pmqa_results,
                                    kwargs={
                                        'pathname': bs.pathname,
                                        'device_type': device_type,
                                        'build1': str(m.tag),
                                        'build2': str(match.tag),
                                        }))
                        break
                tr = match.test_runs[0]
                device_types_with_results.append({
                    'sn': bs.slug,
                    'device_type': device_type,
                    'date': tr.bundle.uploaded_on,
                    'build': match.tag,
                    'link': tr.get_absolute_url(),
                    'width': 0,
                    'last_difference': last_difference,
                    'filter_link': reverse(pmqa_filter_view, kwargs=dict(
                        pathname=bs.pathname, device_type=device_type)),
                    })
                for result in tr.test_results.all().select_related('test_case'):
                    prefix = result.test_case.test_case_id.split('.')[0]
                    device_type__result = prefix__device_type_result.setdefault(prefix, {})
                    d = device_type__result.setdefault(device_type, {'pass': 0, 'total': 0, 'present':True})
                    if result.result == result.RESULT_PASS:
                        d['pass'] += 1
                    d['total'] += 1
            if len(device_types_with_results) > c:
                device_types_with_results[c]['width'] = len(device_types_with_results) - c
    results = []
    prefixes = sorted(prefix__device_type_result)
    for prefix in prefixes:
        board_results = []
        for d in device_types_with_results:
            cell_data = prefix__device_type_result[prefix].get(d['device_type'])
            if cell_data is not None:
                if cell_data['total'] == cell_data['pass']:
                    cell_data['css_class'] = 'pass'
                else:
                    cell_data['css_class'] = 'fail'
            else:
                cell_data = {
                    'css_class': 'missing',
                    'present': False,
                    }
            board_results.append(cell_data)
        results.append((prefix, board_results))
    return render_to_response(
        "dashboard_app/pmqa-view.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(pmqa_view),
            'device_types_with_results': device_types_with_results,
            'results': results,
        }, RequestContext(request))


def pmqa_filter_view_json(request, pathname, device_type):
    test = Test.objects.get(test_id='pwrmgmt')
    bs = BundleStream.objects.get(pathname=pathname)
    filter_data = {
        'bundle_streams': [bs],
        'attributes': [('target.device_type', device_type)],
        'tests': [{'test':test, 'test_cases':[]}],
        'build_number_attribute': 'build.id',
        }
    return FilterTable.json(request, params=(request.user, filter_data))


@BreadCrumb(
    "PMQA results for {pathname} on {device_type}",
    parent=pmqa_view,
    needs=['pathname', 'device_type'])
def pmqa_filter_view(request, pathname, device_type):
    test = Test.objects.get(test_id='pwrmgmt')
    bs = BundleStream.objects.get(pathname=pathname)
    filter_data = {
        'bundle_streams': [bs],
        'attributes': [('target.device_type', device_type)],
        'tests': [{'test':test, 'test_cases':[]}],
        'build_number_attribute': 'build.id',
        }
    return render_to_response(
        "dashboard_app/pmqa_filter.html", {
            'filter_table': FilterTable(
                "filter-table",
                reverse(
                    pmqa_filter_view_json,
                    kwargs=dict(
                        pathname=pathname,
                        device_type=device_type)),
                params=(request.user, filter_data)),
            'bundle_stream': bs.slug,
            'device_type': device_type,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                pmqa_filter_view,
                pathname=pathname,
                device_type=device_type),
        }, RequestContext(request))


@BreadCrumb(
    "Comparing builds {build1} and {build2}",
    parent=pmqa_filter_view,
    needs=['pathname', 'device_type', 'build1', 'build2'])
def compare_pmqa_results(request, pathname, device_type, build1, build2):
    test = Test.objects.get(test_id='pwrmgmt')
    bs = BundleStream.objects.get(pathname=pathname)
    filter_data = {
        'bundle_streams': [bs],
        'attributes': [('target.device_type', device_type)],
        'tests': [{'test':test, 'test_cases':[]}],
        'build_number_attribute': 'build.id',
        }
    test_run_info = compare_filter_matches(request.user, filter_data, build1, build2)
    return render_to_response(
        "dashboard_app/filter_compare_matches.html", {
            'test_run_info': test_run_info,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                compare_pmqa_results,
                pathname=pathname,
                device_type=device_type,
                build1=build1,
                build2=build2),
        }, RequestContext(request))

