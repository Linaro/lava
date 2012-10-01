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


from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.views.decorators.http import require_POST

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from dashboard_app.models import (
    LaunchpadBug,
    Image,
    ImageSet,
    TestRun,
)
from dashboard_app.views import index


@BreadCrumb("Image Reports", parent=index)
def image_report_list(request):
    imagesets = ImageSet.objects.filter()
    imagesets_data = []
    for imageset in imagesets:
        images_data = []
        for image in imageset.images.all():
            # Migration hack: Image.filter cannot be auto populated, so ignore
            # images that have not been migrated to filters for now.
            if image.filter:
                image_data = {
                    'name': image.name,
                    'bundle_count': image.filter.get_test_runs(request.user).count(),
                    'link': image.name,
                    }
                images_data.append(image_data)
        images_data.sort(key=lambda d:d['name'])
        imageset_data = {
            'name': imageset.name,
            'images': images_data,
            }
        imagesets_data.append(imageset_data)
    imagesets_data.sort(key=lambda d:d['name'])
    return render_to_response(
        "dashboard_app/image-reports.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(image_report_list),
            'imagesets': imagesets_data,
        }, RequestContext(request))


@BreadCrumb("{name}", parent=image_report_list, needs=['name'])
def image_report_detail(request, name):

    image = Image.objects.get(name=name)
    matches = image.filter.get_test_runs(request.user, prefetch_related=['launchpad_bugs'])[:50]

    build_number_to_cols = {}

    test_run_names = set()

    for match in matches:
        for test_run in match.test_runs:
            name = test_run.test.test_id
            denorm = test_run.denormalization
            if denorm.count_pass == denorm.count_all():
                cls = 'present pass'
            else:
                    cls = 'present fail'
            bug_ids = sorted([b.bug_id for b in test_run.launchpad_bugs.all()])
            test_run_data = dict(
                present=True,
                cls=cls,
                uuid=test_run.analyzer_assigned_uuid,
                passes=denorm.count_pass,
                total=denorm.count_all(),
                link=test_run.get_permalink(),
                bug_ids=bug_ids,
                )
            if match.tag not in build_number_to_cols:
                # This assumes 1 bundle per match...
                build_number_to_cols[match.tag] = {
                    'test_runs': {},
                    'number': match.tag,
                    'date': test_run.bundle.uploaded_on,
                    'link': test_run.bundle.get_absolute_url(),
                    }
            build_number_to_cols[match.tag]['test_runs'][name] = test_run_data
            if name != 'lava':
                test_run_names.add(name)


    test_run_names = sorted(test_run_names)
    test_run_names.insert(0, 'lava')

    cols = [c for n, c in sorted(build_number_to_cols.items())]

    table_data = []

    for test_run_name in test_run_names:
        row_data = []
        for col in cols:
            test_run_data = col['test_runs'].get(test_run_name)
            if not test_run_data:
                test_run_data = dict(
                    present=False,
                    cls='missing',
                    )
            row_data.append(test_run_data)
        table_data.append(row_data)

    return render_to_response(
        "dashboard_app/image-report.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_report_detail, name=image.name),
            'image': image,
            'cols': cols,
            'table_data': table_data,
            'test_run_names': test_run_names,
        }, RequestContext(request))


@require_POST
def link_bug_to_testrun(request):
    testrun = get_object_or_404(TestRun, analyzer_assigned_uuid=request.POST['uuid'])
    bug_id = request.POST['bug']
    lpbug = LaunchpadBug.objects.get_or_create(bug_id=int(bug_id))[0]
    testrun.launchpad_bugs.add(lpbug)
    testrun.save()
    return HttpResponseRedirect(request.POST['back'])


@require_POST
def unlink_bug_and_testrun(request):
    testrun = get_object_or_404(TestRun, analyzer_assigned_uuid=request.POST['uuid'])
    bug_id = request.POST['bug']
    lpbug = LaunchpadBug.objects.get_or_create(bug_id=int(bug_id))[0]
    testrun.launchpad_bugs.remove(lpbug)
    testrun.save()
    return HttpResponseRedirect(request.POST['back'])
