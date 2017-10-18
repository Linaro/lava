# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Lava Dashboard.
#
# Lava Dashboard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Dashboard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

"""
URL mappings for the Dashboard application

https://docs.djangoproject.com/en/1.8/topics/http/urls/#naming-url-patterns
https://docs.djangoproject.com/en/1.8/releases/1.8/#passing-a-dotted-path-to-reverse-and-url

Avoid letting the name attribute of a url look like a python path - use underscore
instead of period. The name is just a label, using it as a path is deprecated and
support will be removed in Django1.10. Equally, always provide a name if the URL
needs to be reversed elsewhere in the code, e.g. the view. (Best practice is to
use a name for all new urls, even if not yet used elsewhere.)
"""
from django.conf.urls import url
from dashboard_app.views import (
    attachment_download,
    attachment_view,
    bundle_detail,
    bundle_export,
    bundle_json,
    bundle_list,
    bundle_list_export,
    bundle_stream_list,
    bundlestreams_json,
    index,
    mybundlestreams,
    my_subscriptions,
    test_run_detail,
    test_run_export,
    test_run_update_attribute,
    test_result_update_comments,
    test_run_remove_attribute,
    test_result_detail,
    test_result_update_units,
    test_result_update_attribute,
    test_result_remove_attribute,
    test_run_hardware_context,
    test_run_software_context,
    test_run_list,
    redirect_to_bundle,
    redirect_to_test_run,
    redirect_to_test_result,
)

from dashboard_app.views.filters.views import (
    compare_matches,
    filter_add,
    filter_add_cases_for_test_json,
    filter_attr_name_completion_json,
    filter_attr_value_completion_json,
    filter_copy,
    filter_delete,
    filter_detail,
    filter_edit,
    filters_list,
    filter_name_list_json,
    filter_subscribe,
    get_tests_json,
    get_test_cases_json,
)

from dashboard_app.views.images import (
    image_report_detail as images_report_detail,
    image_report_list as images_report_list,
)

from dashboard_app.views.image_reports.views import (
    get_chart_test_data,
    get_group_names,
    image_chart_add,
    image_chart_detail,
    image_chart_delete,
    image_chart_edit,
    image_chart_export,
    image_chart_settings_update,
    image_chart_filter_add,
    image_chart_filter_detail,
    image_chart_filter_delete,
    image_chart_filter_edit,
    image_chart_filter_type_check,
    image_report_list,
    image_report_display,
    image_report_detail,
    image_report_add_group,
    image_report_select_group,
    image_report_order_update,
    image_report_edit,
    image_report_add,
    image_report_group_list,
    image_report_delete,
    image_report_publish,
    image_report_unpublish,
)
from dashboard_app.views import (
    link_bug_to_testrun,
    unlink_bug_and_testrun,
    link_bug_to_testresult,
    unlink_bug_and_testresult
)


urlpatterns = [
    url(r'^$', index, name='lava_dashboard'),
]
