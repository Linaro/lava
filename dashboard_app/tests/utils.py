"""
Django-specific test utilities
"""
import xmlrpclib

from django.conf import settings
from django.contrib.auth import login
from django.core.urlresolvers import reverse
from django.http import HttpRequest
from django.test.client import Client
from django.utils.importlib import import_module

from django_testscenarios.ubertest import (TestCase, TestCaseWithScenarios)


class CSRFTestCase(TestCase):
    """
    Subclass of django's own test.TestCase that allows to interact with cross
    site request forgery protection that is disabled by the regular
    TestCase.

    TODO: Remove this
    """

    def setUp(self):
        super(CSRFTestCase, self).setUp()
        self.client = Client(enforce_csrf_checks=True)


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
    TODO: Remove this
    """


class DashboardXMLRPCViewsTestCase(TestCaseWithScenarios):
    """
    Helper base class for doing XML-RPC requests
    """

    def setUp(self):
        super(DashboardXMLRPCViewsTestCase, self).setUp()
        self.endpoint_path = reverse(
            "dashboard_app.views.dashboard_xml_rpc_handler")

    def xml_rpc_call(self, method, *args):
        request_body = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.client.post(self.endpoint_path,
                request_body, "text/xml")
        return xmlrpclib.loads(response.content)[0][0]
