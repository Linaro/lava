# Copyright (C) 2010 Linaro Limited
#
# Author: Guilherme Salgado <guilherme.salgado@linaro.org>
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
Tests for the login bits of Launch Control.
"""
import cgi
import httplib

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from django_openid_auth.models import UserOpenID
from django_openid_auth.tests.test_views import StubOpenIDProvider

from openid.fetchers import setDefaultFetcher

from dashboard_app.tests.utils import TestClient


class TestOpenIDLogin(TestCase):

    urls = 'django_openid_auth.tests.urls'
    _username = 'someuser'
    _identity_url = 'http://example.com/identity'

    def test_positive_response_from_provider(self):
        self.create_user()
        openid_request = self.initiate_login()

        # Simulate a positive assertion from the server.
        openid_response = openid_request.answer(True)

        # Use that response to complete the authentication.
        response = self.complete(openid_response)

        # And the user is now logged in.
        response = self.client.get('/getuser/')
        self.assertEquals(response.content, self._username)

    def test_negative_response_from_provider(self):
        openid_request = self.initiate_login()

        # Simulate a negative assertion from the server.
        openid_response = openid_request.answer(False)

        # Use that response to complete the authentication.
        response = self.complete(openid_response)

        # Since we got a negative assertion from the server, no user is logged
        # in.
        response = self.client.get('/getuser/')
        self.assertEquals(response.content, '')

    def setUp(self):
        super(TestOpenIDLogin, self).setUp()
        # Use StubOpenIDProvider and _identity_url as our fixed SSO so that
        # we always get a successful OpenID response for _identity_url.
        self.provider = StubOpenIDProvider('http://example.com/')
        setDefaultFetcher(self.provider, wrap_exceptions=False)
        self.missing_sso_server_url = object()
        self.orig_sso_server_url = getattr(
            settings, 'OPENID_SSO_SERVER_URL', self.missing_sso_server_url)
        settings.OPENID_SSO_SERVER_URL = self._identity_url
        self.client = TestClient()

    def tearDown(self):
        super(TestOpenIDLogin, self).tearDown()
        setDefaultFetcher(None)
        if self.orig_sso_server_url == self.missing_sso_server_url:
            del settings.OPENID_SSO_SERVER_URL
        else:
            settings.OPENID_SSO_SERVER_URL = self.orig_sso_server_url

    def create_user(self):
        user = User(username=self._username)
        user.save()
        # Associate our newly created user with the identity URL.
        useropenid = UserOpenID(
            user=user, claimed_id=self._identity_url,
            display_id=self._identity_url)
        useropenid.save()

    def initiate_login(self):
        response = self.client.get('/openid/login/')
        self.assertEqual(httplib.OK, response.status_code)
        openid_request = self.provider.parseFormPost(response.content)
        self.assertTrue(openid_request.return_to.startswith(
            'http://testserver/openid/complete/'))
        return openid_request

    def complete(self, openid_response):
        """Complete an OpenID authentication request."""
        webresponse = self.provider.server.encodeResponse(openid_response)
        self.assertEquals(webresponse.code, 302)
        redirect_to = webresponse.headers['location']
        self.assertTrue(redirect_to.startswith(
            'http://testserver/openid/complete/'))
        return self.client.get('/openid/complete/',
            dict(cgi.parse_qsl(redirect_to.split('?', 1)[1])))
