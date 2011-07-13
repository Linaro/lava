# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
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

"""
Tests for Cross-Site Request Forgery middleware configuration
"""
import xmlrpclib

import django
from django import forms
from django.conf.urls.defaults import patterns, url
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.template import Template, RequestContext

from dashboard_app.tests.utils import CSRFTestCase
from dashboard_app import urls


class CSRFConfigurationTestCase(CSRFTestCase):

    @property
    def urls(self):
        urlpatterns = urls.urlpatterns
        urlpatterns += patterns('', url(r'^test-form/', test_form))
        return type('urls', (), dict(urlpatterns=urlpatterns))

    def setUp(self):
        super(CSRFConfigurationTestCase, self).setUp()
        self.form_path = reverse(test_form)

    def test_csrf_token_present_in_form(self):
        if django.VERSION[:2] == (1, 1):
            # This feature is not supported on django 1.1
            return
        response = self.client.get(self.form_path)
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_cross_site_form_submission_fails(self):
        if django.VERSION[:2] == (1, 1):
            # This feature is not supported on django 1.1
            return
        response = self.client.post(self.form_path, {'text': 'text'})
        self.assertEquals(response.status_code, 403)

    def test_csrf_not_protecting_xml_rpc_views(self):
        """call version and check that we didn't get 403"""
        endpoint_path = reverse('dashboard_app.views.dashboard_xml_rpc_handler')
        request_body = xmlrpclib.dumps((), methodname="version")
        response = self.client.post(endpoint_path, request_body, "text/xml")
        self.assertContains(response, "<methodResponse>", status_code=200)


def test_form(request):
    t = Template(template)
    html = t.render(RequestContext(request, {'form': SingleTextFieldForm()}))
    return HttpResponse(html)


class SingleTextFieldForm(forms.Form):
    text = forms.CharField()


template = """
    <html>
     <body>
      <form action="." method="POST">
      {% csrf_token %} 
       <table>{{ form.as_table }}</table>
      </form>
     </body>
    </html>
    """
