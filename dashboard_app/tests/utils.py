"""
Django-specific test utilities
"""
import os
import xmlrpclib

import os

from django.conf import settings
from django.contrib.auth import login
from django.core.handlers.base import BaseHandler
from django.core.handlers.wsgi import WSGIRequest
from django.core.urlresolvers import reverse
from django.db import close_connection
from django.http import HttpRequest
from django.test.client import Client
from django.utils.importlib import import_module

from django_testscenarios import (TestCase, TestCaseWithScenarios)

from dashboard_app.models import Bundle, BundleStream
from dashboard_app.xmlrpc import DashboardAPI


class UnprotectedClientHandler(BaseHandler):
    """
    A HTTP Handler that can be used for testing purposes.
    Uses the WSGI interface to compose requests, but returns
    the raw HttpResponse object

    This handler does not disable CSRF protection
    """
    def __call__(self, environ):
        from django.conf import settings
        from django.core import signals

        # Set up middleware if needed. We couldn't do this earlier, because
        # settings weren't available.
        if self._request_middleware is None:
            self.load_middleware()

        signals.request_started.send(sender=self.__class__)
        try:
            request = WSGIRequest(environ)
            response = self.get_response(request)

            # Apply response middleware.
            for middleware_method in self._response_middleware:
                response = middleware_method(request, response)
            response = self.apply_response_fixes(request, response)
        finally:
            signals.request_finished.disconnect(close_connection)
            signals.request_finished.send(sender=self.__class__)
            signals.request_finished.connect(close_connection)

        return response


class CSRFClient(Client):
    """
    Subclass of django's own test.client.Client that disables
    the hack used by the regular client to bypass CSRF checks
    """

    def __init__(self, **defaults):
        super(CSRFClient, self).__init__(**defaults)
        self.handler = UnprotectedClientHandler()


class CSRFTestCase(TestCase):
    """
    Subclass of django's own test.TestCase that allows to interact with cross
    site request forgery protection that is disabled by the regular
    TestCase.

    The actual thing happens inside CSRFClient()
    """

    def setUp(self):
        super(CSRFTestCase, self).setUp()
        self.client = CSRFClient()


class TestClient(Client):

    def login_user(self, user):
        """
        Login as specified user, does not depend on auth backend (hopefully)

        This is based on Client.login() with a small hack that does not
        require the call to authenticate()
        """
        if not 'django.contrib.sessions' in settings.INSTALLED_APPS:
            raise EnvironmentError("Unable to login without django.contrib.sessions in INSTALLED_APPS")
        user.backend = "%s.%s" % ("django.contrib.auth.backends",
                                  "ModelBackend")
        engine = import_module(settings.SESSION_ENGINE)

        # Create a fake request to store login details.
        request = HttpRequest()
        if self.session:
            request.session = self.session
        else:
            request.session = engine.SessionStore()
        login(request, user)

        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        self.cookies[session_cookie] = request.session.session_key
        cookie_data = {
            'max-age': None,
            'path': '/',
            'domain': settings.SESSION_COOKIE_DOMAIN,
            'secure': settings.SESSION_COOKIE_SECURE or None,
            'expires': None,
        }
        self.cookies[session_cookie].update(cookie_data)

        # Save the session values.
        request.session.save()


class DashboardViewsTestCase(TestCaseWithScenarios):
    """
    Helper class that ensures dashboard views are mapped in URLs the way
    we expect, regardless of actual deployment.
    """
    urls = 'dashboard_app.urls'

    def setUp(self):
        super(DashboardViewsTestCase, self).setUp()
        self.old_LANGUAGES = settings.LANGUAGES
        self.old_LANGUAGE_CODE = settings.LANGUAGE_CODE
        settings.LANGUAGES = (('en', 'English'),)
        settings.LANGUAGE_CODE = 'en'
        self.old_TEMPLATE_DIRS = settings.TEMPLATE_DIRS
        settings.TEMPLATE_DIRS = (
            os.path.join(
                os.path.dirname(__file__),
                'templates'
            )
        ,)

    def tearDown(self):
        settings.LANGUAGES = self.old_LANGUAGES
        settings.LANGUAGE_CODE = self.old_LANGUAGE_CODE
        settings.TEMPLATE_DIRS = self.old_TEMPLATE_DIRS
        super(DashboardViewsTestCase, self).tearDown()


class DashboardXMLRPCViewsTestCase(DashboardViewsTestCase):
    """
    Helper base class for doing XML-RPC requests
    """

    def setUp(self):
        super(DashboardXMLRPCViewsTestCase, self).setUp()
        self.endpoint_path = reverse(
            "dashboard_app.dashboard_xml_rpc_handler")

    def xml_rpc_call(self, method, *args):
        request_body = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.client.post(self.endpoint_path,
                request_body, "text/xml")
        return xmlrpclib.loads(response.content)[0][0]


class RegressionTestCase(TestCaseWithScenarios):

    def setUp(self):
        super(RegressionTestCase, self).setUp()
        self.bundle_stream = BundleStream.objects.create(
            user=None, group=None)
        self.bundle_stream.save()
        self.regression_data_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'regressions')
        self.dashboard_api = DashboardAPI()

    def tearDown(self):
        Bundle.objects.all().delete()
        super(RegressionTestCase, self).tearDown()

    def get_test_data(self, filename):
        pathname = os.path.join(
            self.regression_data_dir, filename)
        with open(pathname, 'rt') as stream:
            return stream.read()
