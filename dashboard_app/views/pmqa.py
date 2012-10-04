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
    Bundle,
    BundleStream,
    Test,
    TestRunFilter,
)
from dashboard_app.views import index
from dashboard_app.views.filters.forms import FakeTRFTest

bundle_stream_name = '/private/team/linaro/ci-linux-pm-qa/'

@BreadCrumb("PM QA view", parent=index)
def pmqa_view(request):
    b = Bundle.objects.get(content_sha1='bc41959973d2acd5993c3a855cc66638362206a5')
    bs = BundleStream.objects.get(pathname=bundle_stream_name)
    test = Test.objects.get(test_id='pwrmgmt')
    trf_test = FakeTRFTest(test=test)
    trf = TestRunFilter(name='xxxx')
    for i in trf.get_test_runs_impl(request.user, [bs], [('target.device_type', 'panda')], tests=[trf_test])[:1]:
        print i.test_runs
    tr = b.test_runs.filter(test__test_id='pwrmgmt')[0]
    results = {}
    for result in tr.test_results.all().select_related('test_case'):
        prefix = result.test_case.test_case_id.split('.')[0]
        d = results.setdefault(prefix, {'pass': 0, 'total': 0})
        if result.result == result.RESULT_PASS:
            d['pass'] += 1
        d['total'] += 1
    results = sorted(results.items())
    return render_to_response(
        "dashboard_app/pmqa-view.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(pmqa_view),
            'results': results,
        }, RequestContext(request))
