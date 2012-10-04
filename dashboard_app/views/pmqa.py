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


from django.shortcuts import render_to_response
from django.template import RequestContext

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from dashboard_app.models import (
    BundleStream,
    Test,
    TestRunFilter,
)
from dashboard_app.views import index
from dashboard_app.views.filters.forms import FakeTRFTest

bundle_stream_name = '/private/team/linaro/ci-linux-pm-qa/'

@BreadCrumb("PM QA view", parent=index)
def pmqa_view(request):
    bs = BundleStream.objects.get(pathname=bundle_stream_name)
    test = Test.objects.get(test_id='pwrmgmt')
    trf_test = FakeTRFTest(test=test)
    trf = TestRunFilter(build_number_attribute='build.id')
    device_types_with_results = []
    prefix__device_type_result = {}
    for device_type in 'panda', 'beaglexm', 'origen':
        matches = list(
            trf.get_test_runs_impl(
                request.user,
                [bs],
                [('target.device_type', device_type)],
                tests=[trf_test],
                prefetch_related=['test_results'])[:1])
        if matches:
            match = matches[0]
            tr = match.test_runs[0]
            device_types_with_results.append({'device_type': device_type, 'date':tr.bundle.uploaded_on})
            for result in tr.test_results.all().select_related('test_case'):
                prefix = result.test_case.test_case_id.split('.')[0]
                device_type__result = prefix__device_type_result.setdefault(prefix, {})
                d = device_type__result.setdefault(device_type, {'pass': 0, 'total': 0})
                if result.result == result.RESULT_PASS:
                    d['pass'] += 1
                d['total'] += 1
    results = []
    prefixes = sorted(prefix__device_type_result)
    for prefix in prefixes:
        board_results = []
        for d in device_types_with_results:
            board_results.append(prefix__device_type_result[prefix].get(d['device_type']))
        results.append((prefix, board_results))
    return render_to_response(
        "dashboard_app/pmqa-view.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(pmqa_view),
            'device_types_with_results': device_types_with_results,
            'results': results,
        }, RequestContext(request))
