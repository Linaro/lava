# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of django-reports.
#
# django-reports is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# django-reports is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with django-reports.  If not, see <http://www.gnu.org/licenses/>.

"""
Demonstration report
"""

from django import forms
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django_reports.interfaces import IReport
from linaro_json.schema import Schema
from pkg_resources import resource_string
import simplejson as json

from dashboard_app.data_sources import gcc
from dashboard_app.models import Test


class GccBenchmarkReport(IReport):

    settings_schema = Schema({
        "type": "object",
        "properties": {
            "test_id": {
                "type": "string"
            },
            "test_case_id": {
                "type": "string"
            },
            "toolchain_name": {
                "type": "string",
                "optional": True
            },
            "toolchain_branch": {
                "type": "string",
                "optional": True
            },
            "board": {
                "type": "string",
                "optional": True
            },
            "build_variant": {
                "type": "string",
                "optional": True
            }
        },
        "additionalProperties": False,
    })

    def __init__(self, config):
        self.config = config

    def get_data(self):
        data_src_config = {
            "test_id": self.config.settings["test_id"],
            "test_case_id": self.config.settings["test_case_id"],
            "custom_attrs": {
            }
        }
        if self.config.settings.get("toolchain_name"):
            data_src_config["project_name"] = self.config.settings["toolchain_name"]
        if self.config.settings.get("toolchain_branch"):
            data_src_config["branch_url"] = self.config.settings["toolchain_branch"]
        if self.config.settings.get("board"):
            data_src_config["custom_attrs"]["host"] = self.config.settings["board"]
        if self.config.settings.get("build_variant"):
            data_src_config["custom_attrs"]["variant"] = self.config.settings["build_variant"]
        return {
            "series": [
                {
                    "label": " ".join(self.config.settings.values()),
                    "data": gcc.MultiRunBenchmark(data_src_config).get_data(),
                }
            ],
        }


    def render(self, request):
        return render_to_response(
            "dashboard_app/reports/gcc_benchmark.html", {
                "report": self,
                "report_config": self.config,
            }, RequestContext(request)
        )

    @classmethod
    def get_report_name(cls):
        return _(u"GCC Benchmark Report")

    @classmethod
    def get_settings_form(cls):
        class GccBenchmarkReportSettingsForm(forms.Form):

            test_id = forms.ChoiceField(
                label = _(u"Test ID"),
                required = True,
                choices = [
                    (test.test_id, str(test))
                    for test in Test.objects.all()
                ],
            )

            test_case_id = forms.CharField(
                label = _(u"Test case ID"),
                required = True
            )

            board = forms.ChoiceField(
                label = _(u"Board in Michael's Lab"),
                choices = [
                    (name[0], name[0])
                    for name
                    in gcc.AvailableAttributeValues('host').get_data()
                ],
                required = True
            )

            build_variant = forms.ChoiceField(
                label = _(u"Build variant"),
                choices = [
                    (name[0], name[0])
                    for name
                    in gcc.AvailableAttributeValues('variant').get_data()
                ],
                required = False
            )

            toolchain_name = forms.ChoiceField(
                label = _(u"Toolchain"),
                required = True,
                widget = forms.Select,
                choices = [
                    ("gcc", _(u"Upstream GCC")),
                    ("gcc-linaro", _(u"Linaro GCC")),
                ]
            )

            toolchain_branch = forms.CharField(
                label = _(u"Toolchain branch (eg. lp:linaro-gcc/4.5)"),
                required = False
            )
        return GccBenchmarkReportSettingsForm

    @classmethod
    def get_settings_schema(cls):
        return cls.settings_schema
